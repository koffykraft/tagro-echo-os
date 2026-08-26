from __future__ import annotations

import unittest

from src.page_toolbox.model import PageDefinitionError
from src.page_toolbox.renderer import page_from_dict, render_page


class PageToolboxRendererTests(unittest.TestCase):
    def test_definition_renders_to_standalone_responsive_html(self):
        page = page_from_dict({
            "schema": "tagro.echo.page-definition.v1",
            "page_id": "owner-home",
            "title": "Owner Home",
            "target": "responsive",
            "columns": 4,
            "version": 1,
            "components": [
                {"component_id": "sales", "kind": "number", "label": "Sales", "x": 0, "y": 0, "width": 2, "height": 1, "data_binding": "financial.today.sales", "action": None, "visible_on": [], "properties": {"shape": "rounded"}},
                {"component_id": "bill", "kind": "tile", "label": "Bill", "x": 2, "y": 0, "width": 2, "height": 1, "data_binding": None, "action": "navigate:/billing", "visible_on": [], "properties": {}},
            ],
        })
        html = render_page(page)
        self.assertIn("<!doctype html>", html.lower())
        self.assertIn("financial.today.sales", html)
        self.assertIn("navigate:/billing", html)
        self.assertIn("content-security-policy", html.lower())
        self.assertNotIn("<script", html.lower())
        self.assertNotIn("http://", html.lower())
        self.assertNotIn("https://", html.lower())

    def test_declared_action_stays_inert_metadata(self):
        page = page_from_dict({
            "schema": "tagro.echo.page-definition.v1",
            "page_id": "p",
            "title": "P",
            "target": "mobile",
            "columns": 4,
            "version": 1,
            "components": [
                {"component_id": "x", "kind": "button", "label": "Run", "x": 0, "y": 0, "width": 1, "height": 1, "action": "command:stock.count", "visible_on": [], "properties": {}}
            ],
        })
        html = render_page(page)
        self.assertIn('data-action="command:stock.count"', html)
        self.assertNotIn("onclick", html.lower())

    def test_executable_definition_is_refused_before_render(self):
        with self.assertRaises(PageDefinitionError):
            page_from_dict({
                "schema": "tagro.echo.page-definition.v1",
                "page_id": "p",
                "title": "P",
                "target": "responsive",
                "columns": 4,
                "version": 1,
                "components": [
                    {"component_id": "x", "kind": "button", "label": "X", "x": 0, "y": 0, "width": 1, "height": 1, "action": "javascript:alert(1)", "visible_on": [], "properties": {}}
                ],
            })


if __name__ == "__main__":
    unittest.main()
