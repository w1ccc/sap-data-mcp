"""Minimal cached SAP RFC connector backed by PyRFC."""

from __future__ import annotations

import os
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pyrfc import Connection


REQUIRED_SYSTEM_INFO_FIELDS = (
    "System ID",
    "Application Server",
    "System Number",
    "Client",
    "Language",
)

# Reviewed standard read-only function modules. SAPRFCConnector.call rejects
# every other name before anything is sent to SAP (GOLDEN_PATH.md, section 11).
READ_ONLY_FUNCTIONS = frozenset(
    {
        # System
        "RFC_SYSTEM_INFO",
        # Purchase order / production order
        "BAPI_PO_GETDETAIL1",
        "BAPI_PO_GETITEMS",
        "BAPI_INFORECORD_GETLIST",
        "BAPI_CONTRACT_GETDETAIL",
        "BAPI_SAG_GETDETAIL",
        "BAPI_ENTRYSHEET_GETLIST",
        "BAPI_ENTRYSHEET_GETDETAIL",
        "BAPI_PRODORD_GET_LIST",
        "BAPI_PRODORD_GET_DETAIL",
        "BAPI_PRODORDCONF_GETLIST",
        "BAPI_PRODORDCONF_GETDETAIL",
        "BAPI_PLANNEDORDER_GET_DETAIL",
        "BAPI_PROCORD_GET_DETAIL",
        "BAPI_PROCORDCONF_GETLIST",
        "BAPI_PROCORDCONF_GETDETAIL",
        # Sales order list / status
        "BAPI_SALESORDER_GETLIST",
        "BAPI_SALESORDER_GETSTATUS",
        "BAPISDORDER_GETDETAILEDLIST",
        "BAPI_CUSTOMER_GETDETAIL2",
        # Classic WM: reads only
        "BAPI_WHSE_STOCK_GET_LIST",
        "BAPI_WHSE_STOCK_GET_DETAIL",
        "BAPI_WHSE_TO_GET_LIST",
        "BAPI_WHSE_TO_GET_DETAIL",
        # FI standard read functions
        'BAPI_AP_ACC_GETKEYDATEBALANCE',
        'BAPI_AP_ACC_GETOPENITEMS',
        'BAPI_AP_ACC_GETSTATEMENT',
        'BAPI_AR_ACC_GETKEYDATEBALANCE',
        'BAPI_AR_ACC_GETOPENITEMS',
        'BAPI_AR_ACC_GETSTATEMENT',
        'BAPI_BANK_GETDETAIL',
        'BAPI_COMPANYCODE_GETDETAIL',
        'BAPI_COMPANYCODE_GETLIST',
        'BAPI_FIXEDASSET_GETDETAIL',
        'BAPI_FIXEDASSET_GETLIST',
        'BAPI_GL_GETGLACCPERIODBALANCES',
        # CO standard read functions
        'BAPI_CONTROLLINGAREA_GETLIST',
        'BAPI_CONTROLLINGAREA_GETDETAIL',
        'BAPI_ACTIVITYTYPEGRP_GETDETAIL',
        'BAPI_COSTCENTERGROUP_GETDETAIL',
        'BAPI_COSTCENTERGROUP_GETLIST',
        'BAPI_COSTCENTER_GETDETAIL1',
        'BAPI_COSTCENTER_GETLIST1',
        'BAPI_INTERNALORDER_GETDETAIL',
        'BAPI_INTERNALORDER_GETLIST',
        'BAPI_INTERNALORDRGRP_GETDETAIL',
        'BAPI_PROFITCENTERGRP_GETDETAIL',
        'BAPI_PROFITCENTER_GETLIST',
        # QM standard read functions
        'BAPI_INSPLOT_GETDETAIL',
        'BAPI_INSPLOT_GETLIST',
        'BAPI_INSPLOT_GETOPERATIONS',
        'BAPI_INSPOPER_GETDETAIL',
        'BAPI_QUALNOT_GETDETAIL',
        # Material master
        "BAPI_MATERIAL_GETLIST",
        "BAPI_MATERIAL_GET_ALL",
        # Business partner / supplier
        "BAPI_BUPA_SEARCH_2",
        "BAPI_BUPA_CENTRAL_GETDETAIL",
        "BAPI_BUPA_ROLES_GET_2",
        "BAPI_BUPA_ADDRESS_GETDETAIL",
        "BAPI_BUPA_TAX_GETDETAILS",
        "BAPI_BUPA_BANKDETAILS_GET",
        "BAPI_VENDOR_GETDETAIL",
        # Purchase requisition
        "BAPI_PR_GETDETAIL",
        "BAPI_REQUISITION_GETITEMS",
        # Material documents / stock
        "BAPI_GOODSMVT_GETDETAIL",
        "BAPI_GOODSMVT_GETITEMS",
        "BAPI_BATCH_GET_DETAIL",
        "BAPI_MATERIAL_STOCK_REQ_LIST",
        "/SPE/MATERIAL_STOCK_READ",
        # MM invoice verification, physical inventory and reservations: reads only
        "BAPI_INCOMINGINVOICE_GETLIST",
        "BAPI_INCOMINGINVOICE_GETDETAIL",
        "BAPI_MATPHYSINV_GETLIST",
        "BAPI_MATPHYSINV_GETDETAIL",
        "BAPI_RESERVATION_GETITEMS1",
        "BAPI_RESERVATION_GETDETAIL1",
        # ST22 / SM21 / SLG1
        "/SDF/GET_DUMP_LOG",
        "/SDF/GET_SYS_LOG",
        "/SDF/GET_APP_LOG",
        "BAPI_APPLICATIONLOG_GETDETAIL",
        # SM37: the XMI logon/logoff only writes the XMI session audit log.
        "BAPI_XMI_LOGON",
        "BAPI_XMI_LOGOFF",
        "BAPI_XBP_JOB_SELECT",
        "/SDF/GET_JOB_INFO",
        # IDoc
        "/SDF/IMA_DC_IDOC",
        "EDI_DOCUMENT_OPEN_FOR_READ",
        "EDI_DOCUMENT_READ_ALL_STATUS",
        "EDI_SEGMENTS_GET_ALL",
        "EDI_DOCUMENT_CLOSE_READ",
        # qRFC / tRFC / bgRFC
        "TRFC_QIN_OVERVIEW",
        "TRFC_QOUT_OVERVIEW",
        "/SDF/GPC_GET_TRFC_ERRORS",
        "BGRFC_GET_OVERVIEW_INFORMATION",
        # OData service registry of the SAP Gateway hub
        "/IWFND/FM_DOES_SERVICE_EXIST",
        "/IWFND/FM_GET_ALL_SRV_AND_MDL",
        # SE16N-style table display and dictionary field list: reads only. The project
        # owner allowed table reads on 2026-11-10 (GOLDEN_PATH.md, section 11).
        "DDIF_FIELDINFO_GET",
        "RFC_READ_TABLE",
        # ABAP source display (SE38 display): reads only.
        "RPY_PROGRAM_READ",
        # Runs a report and returns its list. It can run any report, so only
        # tools/basis/report_run.py may call it, and only for the display-only reports
        # registered in config/reviewed_reports.json (GOLDEN_PATH.md, section 11).
        "INST_EXECUTE_REPORT",
    }
)

# Function names called in the current context; the tool call audit log sets a
# list here while a tool runs. None means nobody is collecting.
rfc_call_trace: ContextVar[list[str] | None] = ContextVar("rfc_call_trace", default=None)


class SAPRFCConfigurationError(ValueError):
    """Raised when local SAP RFC configuration is incomplete or invalid."""


class SAPRFCConnectionUnavailable(RuntimeError):
    """Raised when a call is attempted before the cached RFC login exists."""


class SAPRFCFunctionNotAllowed(PermissionError):
    """Raised when a function module outside READ_ONLY_FUNCTIONS is requested."""


def _read_system_info(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise SAPRFCConfigurationError(f"SAP System Info is missing: {path.name}")

    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise SAPRFCConfigurationError(
                f"Invalid SAP System Info at line {line_number}; expected 'Field: value'."
            )
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip()

    missing = [field for field in REQUIRED_SYSTEM_INFO_FIELDS if not values.get(field)]
    if missing:
        raise SAPRFCConfigurationError(
            f"Missing SAP System Info fields: {', '.join(missing)}"
        )

    connection_type = values.get("Connection Type", "RFC").upper()
    if connection_type != "RFC":
        raise SAPRFCConfigurationError("Connection Type must be RFC.")

    return values


class SAPRFCConnector:
    """Own one cached PyRFC connection and expose the minimal call interface."""

    def __init__(self, system_info_path: Path, env_path: Path) -> None:
        self._system_info_path = system_info_path
        self._env_path = env_path
        self._system_info: dict[str, str] | None = None
        self._connection: Connection | None = None

    @property
    def is_connected(self) -> bool:
        return self._connection is not None

    @property
    def system_info(self) -> dict[str, str]:
        if self._system_info is None:
            self._system_info = _read_system_info(self._system_info_path)
        return dict(self._system_info)

    def connect(self) -> None:
        if self._connection is not None:
            return

        info = self.system_info
        load_dotenv(self._env_path, override=True)
        username = os.getenv("SAP_USERNAME", "").strip()
        password = os.getenv("SAP_PASSWORD", "")
        if not username or not password:
            raise SAPRFCConfigurationError(
                "SAP RFC credential is missing.\n"
                "Please configure SAP_USERNAME and SAP_PASSWORD in local .env."
            )

        self._connection = Connection(
            ashost=info["Application Server"],
            sysnr=info["System Number"],
            client=info["Client"],
            user=username,
            passwd=password,
            lang=info["Language"],
        )

    def call(self, function_name: str, **params: Any) -> dict[str, Any]:
        if function_name not in READ_ONLY_FUNCTIONS:
            raise SAPRFCFunctionNotAllowed(
                f"{function_name} is not in the reviewed read-only RFC allowlist."
            )
        if self._connection is None:
            raise SAPRFCConnectionUnavailable(
                "RFC login is not established; call test_sap_rfc_connection first "
                "in the same MCP Server session."
            )
        trace = rfc_call_trace.get()
        if trace is not None:
            trace.append(function_name)
        return self._connection.call(function_name, **params)


    def close(self) -> None:
        if self._connection is not None:
            try:
                self._connection.close()
            finally:
                self._connection = None
