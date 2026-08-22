from __future__ import annotations

import unittest

from src.page_builder import PageBuilder, PageValidationError


class PageBuilderExtendedTests(unittest.TestCase):
    def test_chart_list_and_link_are_admitted_and_render_without_script(self):
        page = PageBuilder.definition_from_dict({
            "page_id": "owner-mobile-view",
            "title": "Owner Mobile View",
            "responsive_columns": 4,
            "components": [
                {"component_id": "margin", "kind": "chart", "label": "Margin", "binding": {"path": "financial.margin"}, "width": 2},
                {"component_id": "attention", "kind": "list", "label": "Attention", "binding": {"path": "financial.attention"}, "width": 2},
                {"component_id": "open", "kind": "link", "label": "Open ON CALL", "action": {"kind": "navigate", "target": "on-call.html"}},
            ],
        })
        html = PageBuilder.render_html(page)
        self.assertIn('class="chart"', html)
        self.assertIn('data-bind="financial.attention"', html)
        self.assertIn('data-action="navigate"', html)
        self.assertNotIn("<script", html.lower())

    def test_unsafe_route_is_rejected(self):
        with self.assertRaises(PageValidationError):
            PageBuilder.definition_from_dict({
                "page_id": "unsafe-page",
                "title": "Unsafe",
                "components": [
                    {"component_id": "go", "kind": "button", "label": "Go", "action": {"kind": "navigate", "target": "javascript:alert(1)"}},
                ],
            })

    def test_consequential_owner_action_is_explicitly_discoverable(self):
        page = PageBuilder.definition_from_dict({
            "page_id": "owner-admission",
            "title": "Owner Admission",
            "components": [
                {"component_id": "admit", "kind": "button", "label": "Admit", "action": {"kind": "submit", "target": "financial/admit", "requires_owner": True, "consequential": True}},
            ],
        })
        actions = PageBuilder.consequential_actions(page)
        self.assertEqual(len(actions), 1)
        self.assertTrue(actions[0].requires_owner)
        self.assertTrue(actions[0].consequential)


if __name__ == "__main__":
    unittest.main()
