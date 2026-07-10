"""cfdauto — Excel-driven ANSYS Workbench + Fluent AOA/velocity sweep automation.

Public entry points:

* :func:`cfdauto.config.load_config`
* :class:`cfdauto.orchestrator.Orchestrator` (+ :func:`build_controllers`)
* :class:`cfdauto.excel_manager.ExcelManager`

See ``main.py`` for the CLI and ``README.md`` for the full manual.
"""

__version__ = "0.9.0.dev3"

from .config import Config, load_config                       # noqa: F401
from .models import CaseResult, Experiment                    # noqa: F401
