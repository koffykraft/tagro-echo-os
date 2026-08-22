from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


class PageDefinitionError(ValueError):
    pass


class DeviceTarget(str, Enum):
    MOBILE = "mobile"
    TABLET = "tablet"
    DESKTOP = "desktop"
    RESPONSIVE = "responsive"


class ComponentKind(str, Enum):
    TILE = "tile"
    BUTTON = "button"
    NUMBER = "number"
    TEXT = "text"
    INPUT = "input"
    SEARCH = "search"
    CUSTOMER_PICKER = "customer_picker"
    ITEM_PICKER = "item_picker"
    TABLE = "table"
    LIST = "list"
    STATUS = "status"
    CHART = "chart"
    IMAGE = "image"
    TABS = "tabs"
    DRAWER = "drawer"
    ACTION_BAR = "action_bar"
    LINK = "link"
    AI_ACTION = "ai_action"


ALLOWED_ACTION_PREFIXES = ("navigate:", "query:", "command:", "ai:")


@dataclass(frozen=True)
class PageComponent:
    component_id: str
    kind: ComponentKind
    label: str = ""
    x: int = 0
    y: int = 0
    width: int = 1
    height: int = 1
    data_binding: str | None = None
    action: str | None = None
    visible_on: tuple[DeviceTarget, ...] = ()
    properties: Mapping[str, str] = field(default_factory=dict)

    def validate(self, columns: int) -> None:
        if not self.component_id.strip():
            raise PageDefinitionError("component_id is required")
        if self.x < 0 or self.y < 0:
            raise PageDefinitionError(f"{self.component_id}: x/y must be non-negative")
        if self.width < 1 or self.height < 1:
            raise PageDefinitionError(f"{self.component_id}: width/height must be positive")
        if self.x + self.width > columns:
            raise PageDefinitionError(f"{self.component_id}: component exceeds page columns")
        if self.action and not self.action.startswith(ALLOWED_ACTION_PREFIXES):
            raise PageDefinitionError(
                f"{self.component_id}: action must use a governed action prefix; executable code is not allowed"
            )
        if self.data_binding and any(token in self.data_binding for token in ("(", ")", ";", "<", ">")):
            raise PageDefinitionError(f"{self.component_id}: data_binding must be a declarative path")


@dataclass(frozen=True)
class PageDefinition:
    page_id: str
    title: str
    target: DeviceTarget = DeviceTarget.RESPONSIVE
    columns: int = 4
    components: tuple[PageComponent, ...] = ()
    version: int = 1

    def validate(self) -> None:
        if not self.page_id.strip():
            raise PageDefinitionError("page_id is required")
        if not self.title.strip():
            raise PageDefinitionError("title is required")
        if self.columns < 1 or self.columns > 24:
            raise PageDefinitionError("columns must be between 1 and 24")
        if self.version < 1:
            raise PageDefinitionError("version must be positive")
        ids: set[str] = set()
        for component in self.components:
            if component.component_id in ids:
                raise PageDefinitionError(f"duplicate component_id: {component.component_id}")
            ids.add(component.component_id)
            component.validate(self.columns)

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return {
            "schema": "tagro.echo.page-definition.v1",
            "page_id": self.page_id,
            "title": self.title,
            "target": self.target.value,
            "columns": self.columns,
            "version": self.version,
            "components": [
                {
                    "component_id": c.component_id,
                    "kind": c.kind.value,
                    "label": c.label,
                    "x": c.x,
                    "y": c.y,
                    "width": c.width,
                    "height": c.height,
                    "data_binding": c.data_binding,
                    "action": c.action,
                    "visible_on": [d.value for d in c.visible_on],
                    "properties": dict(c.properties),
                }
                for c in self.components
            ],
        }
