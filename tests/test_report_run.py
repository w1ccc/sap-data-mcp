"""Report runner: only reviewed, unchanged display reports run; selection values and list parsing."""

import json
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

REGISTRY = {
    "ZDEMO_REPORT": {
        "transaction": "ZDEMO1",
        "title": "Demo consumption summary",
        "reviewed_on": "2026-11-10",
        "source_last_changed": "2026-10-21",
        "source_objects": ["ZDEMO_REPORT%", "LZFG_DEMO%"],
        "parameters": {
            "P_WERKS": {"kind": "P", "required": True},
            "P_MONTH": {"kind": "P", "required": True},
            "S_MATNR": {"kind": "S", "material": True},
            "P_MOVED": {"kind": "P"},
        },
        "note": "Selects only.",
    }
}
SOURCE_ROWS = [{"WA": f"{'ZDEMO_REPORT_F01':<40}|20261021"}, {"WA": f"{'LZFG_DEMOU01':<40}|20260914"}]
LIST = [
    {"ZEILE": "-" * 60},
    {"ZEILE": "|Material   |Unit|Previous Period Stock Qty|Current Period Stock Qty|To"},
    {"ZEILE": "-" * 60},
    {"ZEILE": "|10000000011|EA  |                   0.000 |             14,140.000 |"},
    {"ZEILE": "|10000000021|EA  |                  10.000-|              1,000.000"},
    {"ZEILE": "-" * 60},
]


class ReportRun(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / "private_cloud/rfc"))
        from tools.basis import report_run
        cls.runner = report_run

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.registry_path = Path(self.temp.name) / "reviewed_reports.json"
        self.registry_path.write_text(json.dumps(REGISTRY), encoding="utf-8")

    @contextmanager
    def sap(self, connected=True, source=SOURCE_ROWS, run=None):
        calls = []

        def fake(function, **params):
            calls.append((function, params))
            if function == "RFC_READ_TABLE":
                return {"DATA": source}
            return run if run is not None else {"RESULT": "S", "RESULT_TEXT": "Report executed.", "OUTPUT_TAB": LIST}

        with patch.object(self.runner, "_REGISTRY_PATH", self.registry_path), \
                patch.object(self.runner, "sap_rfc", SimpleNamespace(is_connected=connected)), \
                patch.object(self.runner, "call_rfc", side_effect=fake):
            yield calls

    async def test_reviewed_report_runs_with_registered_selection_fields_only(self):
        with self.sap() as calls:
            data = await self.runner.run_report("zdemo1", "p_werks = 1010; P_MONTH = 202608; S_MATNR IN 10000000011, 10000000021; P_MOVED = ''")
        self.assertEqual([function for function, _ in calls], ["RFC_READ_TABLE", "INST_EXECUTE_REPORT"])
        source_check, run = calls[0][1], calls[1][1]
        self.assertEqual(source_check["QUERY_TABLE"], "TRDIR")
        self.assertEqual([option["TEXT"] for option in source_check["OPTIONS"]],
                         ["NAME LIKE 'ZDEMO_REPORT%'", "OR NAME LIKE 'LZFG_DEMO%'"])
        self.assertEqual(run, {"PROGRAM": "ZDEMO_REPORT", "PARA": [
            {"PARA_NAME": "P_WERKS", "PARA_VALUE": "1010"},
            {"PARA_NAME": "P_MONTH", "PARA_VALUE": "202608"},
            {"PARA_NAME": "S_MATNR", "PARA_VALUE": "000000010000000011"},
            {"PARA_NAME": "S_MATNR", "PARA_VALUE": "000000010000000021"},
            {"PARA_NAME": "P_MOVED", "PARA_VALUE": ""}]})
        self.assertEqual((data["status"], data["report"], data["transaction"], data["total_lines"]), ("ok", "ZDEMO_REPORT", "ZDEMO1", 6))
        self.assertEqual(data["columns"], ["Material", "Unit", "Previous Period Stock Qty", "Current Period Stock Qty", "To"])
        self.assertEqual(data["rows"], [
            {"Material": "10000000011", "Unit": "EA", "Previous Period Stock Qty": "0.000", "Current Period Stock Qty": "14,140.000"},
            {"Material": "10000000021", "Unit": "EA", "Previous Period Stock Qty": "10.000-", "Current Period Stock Qty": "1,000.000"}])
        self.assertEqual(data["note"], "Selects only.")

    async def test_report_changed_after_review_is_not_run(self):
        changed = [{"WA": f"{'ZDEMO_REPORT_F01':<40}|20261112"}, {"WA": f"{'ZDEMO_REPORT_TOP':<40}|20260914"}]
        with self.sap(source=changed) as calls:
            data = await self.runner.run_report("ZDEMO_REPORT", "P_WERKS = 1010; P_MONTH = 202608")
        self.assertEqual([function for function, _ in calls], ["RFC_READ_TABLE"])
        self.assertEqual((data["status"], data["error_type"]), ("error", "SourceChangedSinceReview"))
        self.assertEqual(data["changed_objects"], [{"object": "ZDEMO_REPORT_F01", "changed_on": "20261112"}])

    async def test_unreviewed_reports_and_invalid_selections_never_reach_sap(self):
        cases = [
            ("RSUSR003", ""),
            ("ZDEMO_REPORT; X", "P_WERKS = 1010; P_MONTH = 202608"),
            ("ZDEMO_REPORT", "P_WERKS = 1010"),                                       # P_MONTH is required
            ("ZDEMO_REPORT", "P_WERKS = 1010; P_MONTH = 202608; EXECUTION_MODE = BATCH"),  # not a selection field
            ("ZDEMO_REPORT", "P_WERKS = 1010; P_MONTH BETWEEN 202608 AND 202609"),
            ("ZDEMO_REPORT", "P_WERKS IN 1010, 1020; P_MONTH = 202608"),
            ("ZDEMO_REPORT", "P_WERKS = 1010; P_WERKS = 1020; P_MONTH = 202608"),
            ("ZDEMO_REPORT", "P_WERKS = 1010; P_MONTH = 202608; S_MATNR LIKE 10*"),
            ("ZDEMO_REPORT", "P_WERKS = 1010; P_MONTH = 202608; S_MATNR = 'a"),
        ]
        with self.sap() as calls:
            for report, parameters in cases:
                with self.subTest(report=report, parameters=parameters):
                    data = await self.runner.run_report(report, parameters)
                    self.assertEqual(data["error_type"], "ValidationError", data)
            self.assertEqual((await self.runner.run_report("ZDEMO1", "P_WERKS = 1010; P_MONTH = 202608", offset=-1))["error_type"],
                             "ValidationError")
            listing = await self.runner.run_report()
            self.assertEqual(listing["reviewed_reports"]["ZDEMO_REPORT"]["selection_fields"], ["P_WERKS", "P_MONTH", "S_MATNR", "P_MOVED"])
            self.assertEqual(calls, [])
        with self.sap(connected=False) as calls:
            data = await self.runner.run_report("ZDEMO1", "P_WERKS = 1010; P_MONTH = 202608")
            self.assertEqual(data["error_type"], "RFCConnectionUnavailable")
            self.assertEqual(calls, [])

    async def test_sap_refusal_empty_list_and_plain_lists(self):
        with self.sap(run={"RESULT": "E", "RESULT_TEXT": "Berechtigungsprüfung fehlgeschlagen.", "OUTPUT_TAB": []}):
            data = await self.runner.run_report("ZDEMO1", "P_WERKS = 1010; P_MONTH = 202608")
        self.assertEqual((data["status"], data["error_type"]), ("error", "ReportRunFailed"))
        self.assertIn("SA38", data["hint"])
        with self.sap(run={"RESULT": "S", "RESULT_TEXT": "Report executed.", "OUTPUT_TAB": []}):
            data = await self.runner.run_report("ZDEMO1", "P_WERKS = 1010; P_MONTH = 202608")
        self.assertEqual((data["status"], data["lines"]), ("not_found", []))
        with self.sap(run={"RESULT": "S", "OUTPUT_TAB": [{"ZEILE": "Line one"}, {"ZEILE": "Line two"}, {"ZEILE": "Line three"}]}):
            data = await self.runner.run_report("ZDEMO1", "P_WERKS = 1010; P_MONTH = 202608", max_lines=2, offset=1)
        self.assertEqual((data["lines"], data["truncated"], data["next_offset"], data["total_lines"]),
                         (["Line two", "Line three"], False, None, 3))
        self.assertNotIn("rows", data)

    async def test_execute_function_is_allowlisted_for_this_module(self):
        from connectors.sap_rfc_connector import READ_ONLY_FUNCTIONS
        self.assertIn("INST_EXECUTE_REPORT", READ_ONLY_FUNCTIONS)
        shipped = json.loads((ROOT / "private_cloud/rfc/config/reviewed_reports.json").read_text(encoding="utf-8"))
        self.assertEqual({program: entry["transaction"] for program, entry in shipped.items()},
                         {"ZDEMO_REPORT": "ZDEMO1", "ZDEMO_BOM": "ZDEMO2"})
        for entry in shipped.values():
            self.assertTrue(entry["reviewed_on"] and entry["source_last_changed"] and entry["source_objects"])


if __name__ == "__main__":
    unittest.main()
