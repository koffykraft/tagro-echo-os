from __future__ import annotations

import unittest
from pathlib import Path


class PageToolboxV2WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = Path("web/page-toolbox-v2.html").read_text(encoding="utf-8")

    def test_exports_canonical_schema(self):
        self.assertIn("tagro.echo.page-definition.v1", self.text)
        for token in ("page_id", "target", "columns", "components", "data_binding", "visible_on", "properties"):
            self.assertIn(token, self.text)

    def test_component_kinds_align_with_python_model(self):
        for kind in (
            "tile", "button", "number", "text", "input", "search", "customer_picker",
            "item_picker", "table", "list", "status", "chart", "image", "tabs",
            "drawer", "action_bar", "link", "ai_action",
        ):
            self.assertIn(kind, self.text)
        self.assertNotIn("kind:'field'", self.text)
        self.assertNotIn("'heading'", self.text)

    def test_actions_are_declarative_and_governed(self):
        for prefix in ("navigate:", "query:", "command:", "ai:"):
            self.assertIn(prefix, self.text)
        self.assertNotIn("javascript:", self.text.lower())
        self.assertNotIn("eval(", self.text.lower())

    def test_owner_definition_stays_local_until_explicit_export(self):
        self.assertIn("localStorage.setItem('echo.page-definition.'", self.text)
        self.assertIn("Export Definition", self.text)
        self.assertNotIn("fetch(", self.text)
        self.assertNotIn("XMLHttpRequest", self.text)


if __name__ == "__main__":
    unittest.main()
