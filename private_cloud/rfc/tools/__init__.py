"""Register all Private Cloud RFC tools in the established client display order."""

from .platform import system  # noqa: F401
from .basis import connection  # noqa: F401
from .mm import purchasing  # noqa: F401
from .pp import production  # noqa: F401
from .master_data import material, business_partner  # noqa: F401
from .mm import inventory  # noqa: F401
from .basis import monitoring  # noqa: F401
from .basis import table_display  # noqa: F401
from .basis import repository  # noqa: F401
from .basis import report_run  # noqa: F401
from .integration import interface_monitoring, gateway_registry  # noqa: F401
from .platform import audit  # noqa: F401
from .sd import sales  # noqa: F401

from . import wm  # noqa: F401
from . import fi  # noqa: F401
from . import co  # noqa: F401
from . import qm  # noqa: F401
