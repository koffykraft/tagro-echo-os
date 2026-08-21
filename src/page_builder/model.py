from __future__ import annotations

from dataclasses import asdict, dataclass, field
from html import escape
import json
import re
from typing import Iterable, Mapping


ALLOWED_COMPONENTS = {
    "tile",
    "button",
    "field",
    "list",
    "table",
    "chart",
    "link",
    "text",
    "heading",
    "status",
}

_ALLOWED_ACTIONS = {"navigate", "open_form", "submit", "refresh", "export", "filter"}
_ALLOWED_BINDING_ROOTS = {"context", "customer", "product", "stock", "service", "financial", "document", "local"}
_SAFE_ROUTE = re.compile(r"^[A-Za-z0-9_./?&=:%#-]{1,300}$")
_SAFE_BINDING = re.compile(r"^[a-z][a-z0-9_]*(?:\.[A-Za-z0-9_-]+){0,8}$")


class PageValidationError(ValueError):
    pass


@dataclass(frozen=True)
class DataBinding:
    path: str
    mode: str = "read"

    def validate(self) -> None:
        if self.mode not in {"read", "input"}:
            raise PageValidationError(f"unsupported binding mode: {self.mode}")
        if not _SAFE_BINDING.fullmatch(self.path):
            raise PageValidationError(f"invalid binding path: {self.path}")
        root = self.path.split(".", 1)[0]
        if root not in _ALLOWED_BINDING_ROOTS:
            raise PageValidationError(f"binding root is not admitted: {root}")


@dataclass(frozen=True)
class ActionSpec:
    kind: str
    target: str
    requires_owner: bool = False
    consequential: bool = False

    def validate(self) -> None:
        if self.kind not in _ALLOWED_ACTIONS:
            raise PageValidationError(f"unsupported action: {self.kind}")
        if not _SAFE_ROUTE.fullmatch(self.target):
            raise PageValidationError("action target contains unsupported characters")
        if self.consequential and not self.requires_owner:
            raise PageValidationError("consequential page actions must require owner authority")


@dataclass(frozen=True)
class PageComponent:
    component_id: str
    kind: str
    label: str = ""
    binding: DataBinding | None = None
    action: ActionSpec | None = None
    width: int = 1
    options: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", self.component_id):
            raise PageValidationError(f"invalid component id: {self.component_id}")
        if self.kind not in ALLOWED_COMPONENTS:
            raise PageValidationError(f"unsupported component kind: {self.kind}")
        if self.width not in {1, 2, 3, 4}:
            raise PageValidationError("component width must be 1..4")
        if self.binding:
            self.binding.validate()
        if self.action:
            self.action.validate()
        if self.kind == "field" and not self.binding:
            raise PageValidationError("fields require a data binding")
        if self.kind in {"button", "link"} and not self.action:
            raise PageValidationError(f"{self.kind} requires an action")


@dataclass(frozen=True)
class PageDefinition:
    page_id: str
    title: str
    components: tuple[PageComponent, ...]
    version: int = 1
    owner_edit_only: bool = True
    responsive_columns: int = 4
    notes: str = ""

    def validate(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9-]{1,63}", self.page_id):
            raise PageValidationError(f"invalid page id: {self.page_id}")
        if not self.title.strip():
            raise PageValidationError("page title is required")
        if self.version < 1:
            raise PageValidationError("page version must be positive")
        if self.responsive_columns not in {1, 2, 3, 4}:
            raise PageValidationError("responsive_columns must be 1..4")
        seen: set[str] = set()
        for component in self.components:
            component.validate()
            if component.component_id in seen:
                raise PageValidationError(f"duplicate component id: {component.component_id}")
            seen.add(component.component_id)

    def to_json(self) -> str:
        self.validate()
        return json.dumps(asdict(self), ensure_ascii=False, separators=(",", ":"), sort_keys=True)


class PageBuilder:
    """Governed page-definition compiler for owner-composed ECHO pages.

    The builder deliberately compiles only admitted component/action types and
    named data bindings. It never emits caller-supplied JavaScript and it does
    not turn ambiguous page definitions into consequential operations.
    """

    @staticmethod
    def definition_from_dict(payload: Mapping[str, object]) -> PageDefinition:
        components: list[PageComponent] = []
        for raw in payload.get("components", ()) or ():
            if not isinstance(raw, Mapping):
                raise PageValidationError("component must be an object")
            binding_raw = raw.get("binding")
            binding = None
            if binding_raw:
                if not isinstance(binding_raw, Mapping):
                    raise PageValidationError("binding must be an object")
                binding = DataBinding(path=str(binding_raw.get("path", "")), mode=str(binding_raw.get("mode", "read")))
            action_raw = raw.get("action")
            action = None
            if action_raw:
                if not isinstance(action_raw, Mapping):
                    raise PageValidationError("action must be an object")
                action = ActionSpec(
                    kind=str(action_raw.get("kind", "")),
                    target=str(action_raw.get("target", "")),
                    requires_owner=bool(action_raw.get("requires_owner", False)),
                    consequential=bool(action_raw.get("consequential", False)),
                )
            components.append(
                PageComponent(
                    component_id=str(raw.get("component_id", "")),
                    kind=str(raw.get("kind", "")),
                    label=str(raw.get("label", "")),
                    binding=binding,
                    action=action,
                    width=int(raw.get("width", 1)),
                    options=dict(raw.get("options", {}) or {}),
                )
            )
        page = PageDefinition(
            page_id=str(payload.get("page_id", "")),
            title=str(payload.get("title", "")),
            components=tuple(components),
            version=int(payload.get("version", 1)),
            owner_edit_only=bool(payload.get("owner_edit_only", True)),
            responsive_columns=int(payload.get("responsive_columns", 4)),
            notes=str(payload.get("notes", "")),
        )
        page.validate()
        return page

    @staticmethod
    def render_html(page: PageDefinition) -> str:
        page.validate()
        cards = []
        for component in page.components:
            binding = f' data-bind="{escape(component.binding.path)}"' if component.binding else ""
            width = min(component.width, page.responsive_columns)
            label = escape(component.label)
            if component.kind == "heading":
                body = f"<h2>{label}</h2>"
            elif component.kind == "text":
                body = f"<p>{label}</p>"
            elif component.kind == "field":
                body = f'<label>{label}<input{binding} autocomplete="off"></label>'
            elif component.kind in {"button", "link"}:
                action = component.action
                body = (
                    f'<button data-action="{escape(action.kind)}" data-target="{escape(action.target)}"'
                    f' data-owner-required="{str(action.requires_owner).lower()}">{label}</button>'
                )
            elif component.kind == "table":
                body = f'<div class="table-shell"{binding}><strong>{label}</strong><table><tbody></tbody></table></div>'
            elif component.kind == "list":
                body = f'<div{binding}><strong>{label}</strong><ul></ul></div>'
            elif component.kind == "chart":
                body = f'<div class="chart"{binding}><strong>{label}</strong><div class="chart-placeholder">Data view</div></div>'
            else:
                body = f'<div class="{escape(component.kind)}"{binding}>{label}</div>'
            cards.append(f'<section class="component span-{width}" data-component="{escape(component.component_id)}">{body}</section>')

        return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>
:root{{--gap:10px;--border:#d7d7d7;--ink:#171717;--muted:#666;--accent:#e85d22}}
*{{box-sizing:border-box}}body{{margin:0;font:15px system-ui,-apple-system,Segoe UI,sans-serif;color:var(--ink);background:#f6f6f4}}
header{{position:sticky;top:0;background:white;border-bottom:1px solid var(--border);padding:12px 16px;font-weight:800;z-index:4}}
main{{display:grid;grid-template-columns:repeat({cols},minmax(0,1fr));gap:var(--gap);padding:12px;max-width:1240px;margin:auto}}
.component{{background:white;border:1px solid var(--border);border-radius:8px;padding:12px;min-width:0}}.span-2{{grid-column:span 2}}.span-3{{grid-column:span 3}}.span-4{{grid-column:span 4}}
label{{display:grid;gap:5px;font-size:12px;color:var(--muted)}}input,button{{font:inherit;min-height:42px}}input{{width:100%;border:1px solid #aaa;border-radius:6px;padding:8px}}button{{border:0;border-radius:6px;background:var(--accent);color:white;padding:8px 12px;font-weight:700}}
table{{width:100%;border-collapse:collapse}}td,th{{border-bottom:1px solid var(--border);padding:7px}}.chart-placeholder{{min-height:120px;display:grid;place-items:center;color:var(--muted)}}
@media(max-width:760px){{main{{display:block;padding:8px}}.component{{margin-bottom:8px}}header{{padding:10px 12px}}}}
</style></head><body><header>{title}</header><main>{cards}</main></body></html>""".format(
            title=escape(page.title), cols=page.responsive_columns, cards="".join(cards)
        )

    @staticmethod
    def bindings(page: PageDefinition) -> tuple[str, ...]:
        page.validate()
        return tuple(c.binding.path for c in page.components if c.binding)

    @staticmethod
    def consequential_actions(page: PageDefinition) -> tuple[ActionSpec, ...]:
        page.validate()
        return tuple(c.action for c in page.components if c.action and c.action.consequential)
