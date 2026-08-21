from __future__ import annotations

from html import escape
from typing import Mapping, Sequence

from .model import ComponentKind, DeviceTarget, PageComponent, PageDefinition, PageDefinitionError


_KIND_TAG = {
    ComponentKind.BUTTON: "button",
    ComponentKind.INPUT: "input",
    ComponentKind.SEARCH: "input",
    ComponentKind.IMAGE: "div",
    ComponentKind.LINK: "a",
}


def _clean_properties(value: object) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {str(k): str(v) for k, v in value.items() if isinstance(k, str)}


def page_from_dict(payload: Mapping[str, object]) -> PageDefinition:
    if payload.get("schema") != "tagro.echo.page-definition.v1":
        raise PageDefinitionError("unsupported page definition schema")
    raw_components = payload.get("components") or []
    if not isinstance(raw_components, Sequence) or isinstance(raw_components, (str, bytes)):
        raise PageDefinitionError("components must be an array")
    components: list[PageComponent] = []
    for raw in raw_components:
        if not isinstance(raw, Mapping):
            raise PageDefinitionError("component must be an object")
        try:
            visible = tuple(DeviceTarget(str(v)) for v in (raw.get("visible_on") or []))
            component = PageComponent(
                component_id=str(raw.get("component_id") or ""),
                kind=ComponentKind(str(raw.get("kind") or "")),
                label=str(raw.get("label") or ""),
                x=int(raw.get("x") or 0),
                y=int(raw.get("y") or 0),
                width=int(raw.get("width") or 1),
                height=int(raw.get("height") or 1),
                data_binding=str(raw["data_binding"]) if raw.get("data_binding") else None,
                action=str(raw["action"]) if raw.get("action") else None,
                visible_on=visible,
                properties=_clean_properties(raw.get("properties")),
            )
        except (TypeError, ValueError) as exc:
            raise PageDefinitionError("invalid component definition") from exc
        components.append(component)
    try:
        page = PageDefinition(
            page_id=str(payload.get("page_id") or ""),
            title=str(payload.get("title") or ""),
            target=DeviceTarget(str(payload.get("target") or "responsive")),
            columns=int(payload.get("columns") or 4),
            components=tuple(components),
            version=int(payload.get("version") or 1),
        )
    except (TypeError, ValueError) as exc:
        raise PageDefinitionError("invalid page definition") from exc
    page.validate()
    return page


def _component_html(component: PageComponent) -> str:
    kind = component.kind.value
    label = escape(component.label or component.component_id)
    attrs = [
        f'id="{escape(component.component_id, quote=True)}"',
        f'class="echo-component kind-{escape(kind, quote=True)}"',
        f'style="grid-column:{component.x + 1}/span {component.width};grid-row:{component.y + 1}/span {component.height}"',
        f'data-kind="{escape(kind, quote=True)}"',
    ]
    if component.data_binding:
        attrs.append(f'data-binding="{escape(component.data_binding, quote=True)}"')
    if component.action:
        # Actions remain inert declarative metadata in the generated product.
        # A governed runtime may bind admitted actions later.
        attrs.append(f'data-action="{escape(component.action, quote=True)}"')
    if component.visible_on:
        attrs.append(f'data-visible-on="{escape(",".join(v.value for v in component.visible_on), quote=True)}"')
    shape = component.properties.get("shape", "rounded")
    attrs.append(f'data-shape="{escape(shape, quote=True)}"')
    tag = _KIND_TAG.get(component.kind, "section")
    if component.kind in {ComponentKind.INPUT, ComponentKind.SEARCH}:
        input_type = "search" if component.kind == ComponentKind.SEARCH else "text"
        return f'<label {" ".join(attrs)}><span>{label}</span><input type="{input_type}" aria-label="{label}"></label>'
    if component.kind == ComponentKind.LINK:
        return f'<a {" ".join(attrs)} href="#" role="link">{label}</a>'
    if component.kind == ComponentKind.IMAGE:
        return f'<div {" ".join(attrs)} role="img" aria-label="{label}"><span>{label}</span></div>'
    return f'<{tag} {" ".join(attrs)}>{label}</{tag}>'


def render_page(page: PageDefinition) -> str:
    """Render a validated definition into standalone responsive HTML.

    The generated document has no external dependencies and does not execute
    declared business/AI actions. It is therefore a working visual product/prototype,
    not an authority bypass.
    """
    page.validate()
    components = "".join(_component_html(component) for component in page.components)
    title = escape(page.title)
    target = escape(page.target.value, quote=True)
    return f'''<!doctype html>
<html lang="en" data-target="{target}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'">
<title>{title}</title>
<style>
:root{{--cols:{page.columns};font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#171717;background:#f5f5f1}}
*{{box-sizing:border-box}} body{{margin:0;padding:16px}} main{{max-width:1180px;margin:auto}} h1{{font-size:1.35rem;margin:0 0 14px}}
.echo-grid{{display:grid;grid-template-columns:repeat(var(--cols),minmax(0,1fr));grid-auto-rows:minmax(68px,auto);gap:10px}}
.echo-component{{min-width:0;border:1px solid #deded7;background:#fff;border-radius:12px;padding:12px;overflow:auto;text-decoration:none;color:inherit;font:inherit;text-align:left}}
.echo-component[data-shape="square"]{{border-radius:0}} .echo-component[data-shape="pill"]{{border-radius:999px}}
.kind-number{{font-size:1.5rem;font-weight:700}} .kind-tile,.kind-button,.kind-ai_action{{font-weight:700}} label.echo-component span{{display:block;font-size:.78rem;margin-bottom:6px;color:#666}}
label.echo-component input{{width:100%;min-height:42px;border:1px solid #ccc;border-radius:8px;padding:8px;font:inherit}}
@media(max-width:720px){{body{{padding:10px}} .echo-grid{{--cols:min({page.columns},4)}}}}
</style>
</head>
<body><main><h1>{title}</h1><div class="echo-grid">{components}</div></main></body>
</html>'''
