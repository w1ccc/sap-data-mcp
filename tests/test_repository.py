"""ABAP source display tool: RPY_PROGRAM_READ parameters, search with context and paging."""

import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

SOURCE = [{"LINE": text} for text in (
    "REPORT zdemo.",
    "INCLUDE zdemo_top.",
    "* stock",
    "SELECT stock_qty FROM matdoc",
    "  WHERE werks = p_werks.",
    "WRITE 'done'.",
    "",
    "FORM frm_stock.",
    "ENDFORM.",
)]
RESPONSE = {"SOURCE_EXTENDED": SOURCE, "INCLUDE_TAB": [{"INCLNAME": "ZDEMO_TOP"}]}


class RfcFailure(Exception):
    def __init__(self, key, message):
        super().__init__(message)
        self.key, self.message = key, message


class Repository(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / "private_cloud/rfc"))
        from tools.basis import repository
        cls.repository = repository

    @contextmanager
    def sap(self, connected=True, **call):
        with patch.object(self.repository, "sap_rfc", SimpleNamespace(is_connected=connected)), \
                patch.object(self.repository, "call_rfc", **call) as mock:
            yield mock

    async def test_source_lines_are_numbered_paged_and_includes_are_listed(self):
        with self.sap(return_value=RESPONSE) as call:
            data = await self.repository.read_program_source("zdemo", max_lines=3, offset=1)
        self.assertEqual(call.call_args.args, ("RPY_PROGRAM_READ",))
        self.assertEqual(call.call_args.kwargs, {"PROGRAM_NAME": "ZDEMO", "WITH_INCLUDELIST": "X",
                                                 "ONLY_SOURCE": "X", "WITH_LOWERCASE": "X"})
        self.assertEqual((data["status"], data["includes"], data["total_lines"]), ("ok", ["ZDEMO_TOP"], 9))
        self.assertEqual(data["lines"], ["2  INCLUDE zdemo_top.", "3  * stock", "4  SELECT stock_qty FROM matdoc"])
        self.assertEqual((data["returned"], data["truncated"], data["next_offset"], data["matching_lines"]),
                         (3, True, 4, None))

    async def test_search_keeps_hits_with_context_and_marks_them(self):
        with self.sap(return_value=RESPONSE):
            data = await self.repository.read_program_source("ZDEMO", "STOCK_QTY | frm_", context_lines=1)
        self.assertEqual(data["lines"], ["3  * stock", "4* SELECT stock_qty FROM matdoc", "5    WHERE werks = p_werks.",
                                         "7  ", "8* FORM frm_stock.", "9  ENDFORM."])
        self.assertEqual((data["matching_lines"], data["truncated"], data["next_offset"]), (2, False, None))

    async def test_invalid_input_missing_login_and_sap_errors(self):
        from connectors.sap_rfc_connector import READ_ONLY_FUNCTIONS
        with self.sap(return_value=RESPONSE) as call:
            for program, offset in (("ZDEMO; X", 0), ("", 0), ("ZDEMO", -1)):
                data = await self.repository.read_program_source(program, offset=offset)
                self.assertEqual(data["error_type"], "ValidationError")
            self.assertEqual(call.call_count, 0)
        with self.sap(connected=False) as call:
            self.assertEqual((await self.repository.read_program_source("ZDEMO"))["error_type"], "RFCConnectionUnavailable")
            self.assertEqual(call.call_count, 0)
        with self.sap(side_effect=RfcFailure("PERMISSION_ERROR", "No authorization")):
            data = await self.repository.read_program_source("ZDEMO")
        self.assertEqual((data["status"], data["error_key"], data["program"]), ("error", "PERMISSION_ERROR", "ZDEMO"))
        self.assertIn("S_DEVELOP", data["hint"])
        with self.sap(return_value={"SOURCE_EXTENDED": [], "INCLUDE_TAB": []}):
            self.assertEqual((await self.repository.read_program_source("ZDEMO"))["status"], "not_found")
        self.assertIn("RPY_PROGRAM_READ", READ_ONLY_FUNCTIONS)


if __name__ == "__main__":
    unittest.main()
