"""Panel checklist shown when creating a project.

Keys are stable ids stored on ``project_panels``. Selecting a panel does not
attach a data source. That setting is still to be built.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PanelDef:
    key: str
    label: str
    group: str
    description: str


PANELS: tuple[PanelDef, ...] = (
    PanelDef("system-health", "System health", "Server", "Whether the project is up."),
    PanelDef("performance", "Performance", "Server", "Latency and resource use."),
    PanelDef("logs", "Logs", "Server", "Recent log lines."),
    PanelDef("uptime-incidents", "Uptime & incidents", "Server", "Uptime and incident history."),
    PanelDef("deploys-releases", "Deploys/releases", "Server", "Release history."),
    PanelDef(
        "user-data",
        "User data",
        "Users",
        "Daily active, new, and monthly returning.",
    ),
    PanelDef("sales-data", "Sales data", "Financials", "Sales and revenue."),
    PanelDef("consolidated-costs", "Consolidated costs", "Financials", "Cost lines for the project."),
    PanelDef("product-metrics", "Product metrics", "Optional", "Conversion and churn."),
    PanelDef("marketing", "Marketing", "Optional", "Traffic and signups by channel."),
    PanelDef("support", "Support", "Optional", "Tickets and response time."),
    PanelDef(
        "logistics",
        "Logistics",
        "Optional",
        "Orders, inventory, shipments, and delivery status.",
    ),
)

PANELS_BY_KEY: dict[str, PanelDef] = {panel.key: panel for panel in PANELS}
SALES_DATA = "sales-data"


def ordered_panel_keys(selected: set[str]) -> list[str]:
    """Return selected keys in checklist order."""
    return [panel.key for panel in PANELS if panel.key in selected]
