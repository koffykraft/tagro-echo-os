from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PageToolboxWebTests(unittest.TestCase):
    def test_visual_builder_emits_governed_page_definition_schema(self):
        text = (ROOT / "web" / "page-builder.html").read_text(encoding="utf-8")
        self.assertIn("tagro.echo.page-definition.v1", text)
        self.assertIn("data_binding", text)
        self.assertIn("action", text)
        self.assertIn("visible_on", text)
        self.assertIn("properties", text)

    def test_builder_has_no_dynamic_code_execution(self):
        text = (ROOT / "web" / "page-builder.html").read_text(encoding="utf-8").lower()
        self.assertNotIn("eval(", text)
        self.assertNotIn("new function", text)
        self.assertNotIn("javascript:", text)

    def test_builder_is_phone_aware_and_grid_resizable(self):
        text = (ROOT / "web" / "page-builder.html").read_text(encoding="utf-8")
        self.assertIn('option>mobile</option>', text)
        self.assertIn('id="width"', text)
        self.assertIn('id="height"', text)
        self.assertIn('wireDrag', text)

    def test_builder_is_linked_and_cached(self):
        index = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        sw = (ROOT / "web" / "sw.js").read_text(encoding="utf-8")
        self.assertIn('href="page-builder.html"', index)
        self.assertIn("'./page-builder.html'", sw)

    def test_preview_generates_standalone_product_without_admitting_actions(self):
        text = (ROOT / "web" / "page-builder.html").read_text(encoding="utf-8")
        self.assertIn('id="preview"', text)
        self.assertIn("function renderProduct(def)", text)
        self.assertIn("Content-Security-Policy", text)
        self.assertIn("declared business/AI actions remain inert", text)
        self.assertIn("navigate:", text)
        self.assertIn("query:", text)
        self.assertIn("command:", text)
        self.assertIn("ai:", text)
        self.assertIn("unsafeBinding", text)


if __name__ == "__main__":
    unittest.main()
