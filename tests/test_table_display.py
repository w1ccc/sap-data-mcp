"""SE16N-style table display tools: input validation, RFC_READ_TABLE parameters and row parsing."""

import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def column(name, offset, length, kind, text=""):
    return {"FIELDNAME": name, "OFFSET": f"{offset:06d}", "LENGTH": f"{length:06d}", "TYPE": kind, "FIELDTEXT": text}


MATDOC_COLUMNS = [column("MBLNR", 0, 10, "C", "Material Document"), column("BWART", 10, 3, "C"),
                  column("STOCK_QTY", 13, 16, "P", "Stock Quantity")]


def matdoc_row(document, movement, quantity):
    return {"WA": f"{document:<10}{movement:<3}{quantity:>16}"}


class RfcFailure(Exception):
    def __init__(self, key, message):
        super().__init__(message)
        self.key, self.message = key, message


class TableDisplay(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / "private_cloud/rfc"))
        from tools.basis import table_display
        cls.table = table_display

    def setUp(self):
        self.table._sorted_rows_supported = True

    @contextmanager
    def sap(self, **call):
        with patch.object(self.table, "sap_rfc", SimpleNamespace(is_connected=True)), \
                patch.object(self.table, "call_rfc", **call) as mock:
            yield mock

    async def test_read_table_quotes_filter_values_and_slices_fixed_width_rows(self):
        response = {"FIELDS": MATDOC_COLUMNS, "DATA": [matdoc_row("4900004467", "261", "20.000-"),
                                                       matdoc_row("4900004468", "101", "10.000"),
                                                       matdoc_row("4900004469", "101", "1.000")]}
        where = "werks = 1010; BUDAT BETWEEN 20260814 AND '20260817'; BWART IN 101, 261; MATNR like 4000*; CHARG = 'O''B'"
        with self.sap(return_value=response) as call:
            data = await self.table.read_table("matdoc", "mblnr, bwart stock_qty", where, max_results=2)
        self.assertEqual(call.call_args.args, ("RFC_READ_TABLE",))
        sent = call.call_args.kwargs
        self.assertEqual((sent["QUERY_TABLE"], sent["DELIMITER"], sent["GET_SORTED"]), ("MATDOC", "", "X"))
        self.assertEqual((sent["ROWSKIPS"], sent["ROWCOUNT"]), (0, 3))
        self.assertEqual(sent["FIELDS"], [{"FIELDNAME": "MBLNR"}, {"FIELDNAME": "BWART"}, {"FIELDNAME": "STOCK_QTY"}])
        lines = [option["TEXT"] for option in sent["OPTIONS"]]
        self.assertTrue(all(len(line) <= 72 for line in lines), lines)
        self.assertEqual(" ".join(lines), "WERKS = '1010' AND BUDAT BETWEEN '20260814' AND '20260817' AND "
                                          "BWART IN ( '101', '261' ) AND MATNR LIKE '4000%' AND CHARG = 'O''B'")
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["rows"], [{"MBLNR": "4900004467", "BWART": "261", "STOCK_QTY": "-20.000"},
                                        {"MBLNR": "4900004468", "BWART": "101", "STOCK_QTY": "10.000"}])
        self.assertEqual((data["returned"], data["truncated"], data["next_offset"]), (2, True, 2))
        self.assertEqual(data["columns"][2], {"name": "STOCK_QTY", "type": "P", "length": 16, "text": "Stock Quantity"})

    async def test_read_table_reports_no_rows_and_keeps_the_offset(self):
        with self.sap(return_value={"FIELDS": MATDOC_COLUMNS, "DATA": []}) as call:
            data = await self.table.read_table("MATDOC", "MBLNR,BWART,STOCK_QTY", max_results=5000, offset=40)
        self.assertEqual((call.call_args.kwargs["ROWSKIPS"], call.call_args.kwargs["ROWCOUNT"]), (40, 1001))
        self.assertEqual(call.call_args.kwargs["OPTIONS"], [])
        self.assertEqual((data["status"], data["rows"], data["truncated"], data["next_offset"]), ("not_found", [], False, None))

    async def test_invalid_input_never_reaches_sap(self):
        cases = [
            ("USR02", "BNAME", ""),                       # password hashes are refused
            ("MATDOC; X", "MBLNR", ""),
            ("MATDOC", "", ""),
            ("MATDOC", "MBLNR;", ""),
            ("MATDOC", "MBLNR", "SELECT * FROM USR02"),
            ("MATDOC", "MBLNR", "1WERKS = 3"),
            ("MATDOC", "MBLNR", "WERKS = 'a"),
            ("MATDOC", "MBLNR", "WERKS = 1010' OR '1' = '1"),
            ("MATDOC", "MBLNR", "WERKS ="),
            ("MATDOC", "MBLNR", "BUDAT BETWEEN 20260801"),
            ("MATDOC", "MBLNR", "WERKSIN 1010"),
            ("MATDOC", "MBLNR", "HEADER_TXT = " + "x" * 80),
        ]
        with self.sap(return_value={}) as call:
            for table, fields, where in cases:
                with self.subTest(table=table, fields=fields, where=where):
                    data = await self.table.read_table(table, fields, where)
                    self.assertEqual(data["error_type"], "ValidationError", data)
            self.assertEqual((await self.table.read_table("MATDOC", "MBLNR", offset=-1))["error_type"], "ValidationError")
            self.assertEqual((await self.table.list_table_fields("RFCDES"))["error_type"], "ValidationError")
            self.assertEqual((await self.table.summarize_table("MATDOC", ""))["error_type"], "ValidationError")
            self.assertEqual(call.call_count, 0)

    async def test_quotes_inside_a_quoted_value_stay_one_literal(self):
        with self.sap(return_value={"FIELDS": MATDOC_COLUMNS, "DATA": []}) as call:
            await self.table.read_table("MATDOC", "MBLNR", "BKTXT = '1010'' OR ''1'' = ''1'; SGTXT = ''")
        self.assertEqual([option["TEXT"] for option in call.call_args.kwargs["OPTIONS"]],
                         ["BKTXT = '1010'' OR ''1'' = ''1' AND SGTXT = ''"])

    async def test_long_in_list_wraps_at_72_characters_between_values(self):
        materials = [f"0000000400090{index:05d}" for index in range(12)]
        with self.sap(return_value={"FIELDS": MATDOC_COLUMNS, "DATA": []}) as call:
            await self.table.read_table("MATDOC", "MBLNR", "MATBF NOT IN (" + ", ".join(materials) + ")")
        lines = [option["TEXT"] for option in call.call_args.kwargs["OPTIONS"]]
        self.assertGreater(len(lines), 3)
        self.assertTrue(all(len(line) <= 72 for line in lines), lines)
        self.assertEqual(" ".join(lines), "MATBF NOT IN ( " + ", ".join(f"'{m}'" for m in materials) + " )")

    async def test_older_rfc_read_table_without_get_sorted_is_retried_once(self):
        calls = []

        def fake(function, **params):
            calls.append(params)
            if "GET_SORTED" in params:
                raise RfcFailure("RFC_INVALID_PARAMETER", "field 'GET_SORTED' not found")
            return {"FIELDS": MATDOC_COLUMNS, "DATA": [matdoc_row("1", "101", "5.000")]}

        with self.sap(side_effect=fake):
            first = await self.table.read_table("MATDOC", "MBLNR,BWART,STOCK_QTY")
            await self.table.read_table("MATDOC", "MBLNR,BWART,STOCK_QTY")
        self.assertEqual(first["rows"][0]["STOCK_QTY"], "5.000")
        self.assertEqual(["GET_SORTED" in params for params in calls], [True, False, False])

    async def test_rfc_errors_keep_the_sap_key_and_add_a_hint(self):
        with self.sap(side_effect=RfcFailure("NOT_AUTHORIZED", "No authorization for table MATDOC")):
            data = await self.table.read_table("MATDOC", "MBLNR")
        self.assertEqual((data["status"], data["error_key"], data["table"]), ("error", "NOT_AUTHORIZED", "MATDOC"))
        self.assertIn("S_TABU_NAM", data["hint"])

    async def test_summarize_table_totals_per_group_and_flags_partial_scans(self):
        columns = [column("BWART", 0, 3, "C"), column("STOCK_QTY", 3, 16, "P")]
        rows = [{"WA": f"{movement:<3}{quantity:>16}"} for movement, quantity in
                (("261", "20.000-"), ("101", "10.000"), ("261", "18.000-"), ("101", "0.500"))]

        def fake(function, **params):
            return {"FIELDS": columns} if params.get("NO_DATA") == "X" else {"FIELDS": columns, "DATA": rows}

        with self.sap(side_effect=fake) as call:
            data = await self.table.summarize_table("MATDOC", "STOCK_QTY", "BWART", "WERKS = 1010")
            self.assertEqual(call.call_args.kwargs["ROWCOUNT"], 20001)
            self.assertEqual(call.call_args.kwargs["FIELDS"], [{"FIELDNAME": "BWART"}, {"FIELDNAME": "STOCK_QTY"}])
            self.assertEqual(data["groups"], [{"BWART": "101", "rows": 2, "STOCK_QTY": "10.500"},
                                              {"BWART": "261", "rows": 2, "STOCK_QTY": "-38.000"}])
            self.assertEqual(data["total"], {"rows": 4, "STOCK_QTY": "-27.500"})
            self.assertEqual((data["complete"], data["rows_scanned"]), (True, 4))
            partial = await self.table.summarize_table("MATDOC", "STOCK_QTY", max_scan_rows=3)
            self.assertEqual((partial["complete"], partial["rows_scanned"], partial["total"]["STOCK_QTY"]),
                             (False, 3, "-28.000"))
            count = call.call_count
            data = await self.table.summarize_table("MATDOC", "BWART")
            self.assertEqual(data["error_type"], "ValidationError")
            self.assertEqual(call.call_count, count + 1)  # only the field metadata was read

    async def test_list_table_fields_filters_by_name_or_text_and_pages(self):
        fields = [{"FIELDNAME": "MANDT", "KEYFLAG": "X", "DATATYPE": "CLNT", "LENG": "000003", "DECIMALS": "000000", "FIELDTEXT": "Client"},
                  {"FIELDNAME": "STOCK_QTY", "KEYFLAG": "", "DATATYPE": "QUAN", "LENG": "000031", "DECIMALS": "000014", "FIELDTEXT": "Stock Quantity"},
                  {"FIELDNAME": "MENGE", "KEYFLAG": "", "DATATYPE": "QUAN", "LENG": "000013", "DECIMALS": "000003", "FIELDTEXT": "Quantity"},
                  {"FIELDNAME": "BUDAT", "KEYFLAG": "", "DATATYPE": "DATS", "LENG": "000008", "DECIMALS": "000000", "FIELDTEXT": "Posting Date"}]
        with self.sap(return_value={"DFIES_TAB": fields}) as call:
            data = await self.table.list_table_fields("matdoc", "quantity")
            self.assertEqual(call.call_args.args, ("DDIF_FIELDINFO_GET",))
            self.assertEqual(call.call_args.kwargs, {"TABNAME": "MATDOC", "ALL_TYPES": "X"})
            self.assertEqual([field["name"] for field in data["fields"]], ["STOCK_QTY", "MENGE"])
            self.assertEqual(data["fields"][0], {"name": "STOCK_QTY", "key": False, "type": "QUAN", "length": 31,
                                                 "decimals": 14, "text": "Stock Quantity"})
            paged = await self.table.list_table_fields("MATDOC", max_results=2, offset=1)
            self.assertEqual(([field["name"] for field in paged["fields"]], paged["total"], paged["truncated"]),
                             (["STOCK_QTY", "MENGE"], 4, True))
            self.assertEqual((await self.table.list_table_fields("MATDOC", "B*T"))["fields"][0]["name"], "BUDAT")
            self.assertEqual((await self.table.list_table_fields("MATDOC", "ZZ*"))["status"], "not_found")

    async def test_without_login_nothing_is_called_and_the_functions_are_allowlisted(self):
        from connectors.sap_rfc_connector import READ_ONLY_FUNCTIONS
        with patch.object(self.table, "sap_rfc", SimpleNamespace(is_connected=False)), \
                patch.object(self.table, "call_rfc") as call:
            for result in (await self.table.read_table("MATDOC", "MBLNR"),
                           await self.table.summarize_table("MATDOC", "STOCK_QTY"),
                           await self.table.list_table_fields("MATDOC")):
                self.assertEqual(result["error_type"], "RFCConnectionUnavailable")
            self.assertEqual(call.call_count, 0)
        self.assertLessEqual({"RFC_READ_TABLE", "DDIF_FIELDINFO_GET"}, READ_ONLY_FUNCTIONS)


if __name__ == "__main__":
    unittest.main()
