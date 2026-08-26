from __future__ import annotations

import unittest

from src.page_builder import (
    ActionSpec,
    DataBinding,
    PageBuilder,
    PageComponent,
    PageDefinition,
    PageValidationError,
)


class PageBuilderTests(unittest.TestCase):
    def test_owner_composed_page_renders_responsive_safe_html(self):
        page = PageDefinition(
            page_id="owner-on-call",
            title="Owner ON CALL",
            components=(
                PageComponent("sales", "tile", "Sales", DataBinding("financial.sales")),
                PageComponent("branch", "field", "Branch", DataBinding("context.branch", "input")),
                PageComponent("health", "table", "Financial health", DataBinding("financial.branch_summary"), width=3),
                PageComponent("refresh", "button", "Refresh", action=ActionSpec("refresh", "financial/on-call")),
            ),
        )
        html = PageBuilder.render_html(page)
        self.assertIn('data-bind="financial.sales"', html)
        self.assertIn('data-component="health"', html)
        self.assertIn("@media(max-width:760px)", html)
        self.assertNotIn("<script", html.lower())

    def test_consequential_action_requires_owner(self):
        page = PageDefinition(
            page_id="bad-action",
            title="Bad action",
            components=(
                PageComponent(
                    "submit",
                    "button",
                    "Submit",
                    action=ActionSpec("submit", "billing/admit", consequential=True),
                ),
            ),
        )
        with self.assertRaises(PageValidationError):
            page.validate()

    def test_unknown_binding_root_is_rejected(self):
        page = PageDefinition(
            page_id="bad-binding",
            title="Bad binding",
            components=(PageComponent("x", "tile", "X", DataBinding("secret.password")),),
        )
        with self.assertRaises(PageValidationError):
            page.validate()

    def test_definition_from_dict_round_trip_preserves_governed_shape(self):
        payload = {
            "page_id": "stock-count",
            "title": "Stock Count",
            "owner_edit_only": True,
            "responsive_columns": 4,
            "components": [
                {"component_id": "part", "kind": "field", "label": "Part", "binding": {"path": "product.part", "mode": "input"}},
                {"component_id": "stock", "kind": "status", "label": "Available", "binding": {"path": "stock.available"}, "width": 2},
                {"component_id": "save", "kind": "button", "label": "Save draft", "action": {"kind": "submit", "target": "stock/draft"}},
            ],
        }
        page = PageBuilder.definition_from_dict(payload)
        self.assertEqual(page.page_id, "stock-count")
        self.assertEqual(PageBuilder.bindings(page), ("product.part", "stock.available"))
        self.assertIn('data-action="submit"', PageBuilder.render_html(page))
        self.assertIn('"owner_edit_only":true', page.to_json())

    def test_ai_generated_html_cannot_inject_arbitrary_script_through_labels(self):
        page = PageDefinition(
            page_id="escaped-page",
            title='<script>alert("x")</script>',
            components=(PageComponent("h", "heading", '<img src=x onerror=alert(1)>'),),
        )
        html = PageBuilder.render_html(page)
        self.assertNotIn("<script>alert", html)
        self.assertNotIn("<img src=x", html)
        self.assertIn("&lt;script&gt;", html)


if __name__ == "__main__":
    unittest.main()
