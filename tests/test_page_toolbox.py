from __future__ import annotations

import unittest

from src.page_toolbox.model import ComponentKind, DeviceTarget, PageComponent, PageDefinition, PageDefinitionError


class PageToolboxTests(unittest.TestCase):
    def test_owner_can_define_mobile_layout_declaratively(self):
        page = PageDefinition(
            page_id="owner-home",
            title="Owner ON CALL",
            target=DeviceTarget.MOBILE,
            columns=4,
            components=(
                PageComponent("sales", ComponentKind.NUMBER, "Sales Today", 0, 0, 4, 1, "financial.today.sales"),
                PageComponent("gp", ComponentKind.NUMBER, "Gross Profit", 0, 1, 2, 1, "financial.today.gross_profit"),
                PageComponent("bill", ComponentKind.TILE, "BILL", 0, 2, 1, 1, action="navigate:/billing"),
            ),
        )
        payload = page.to_dict()
        self.assertEqual(payload["schema"], "tagro.echo.page-definition.v1")
        self.assertEqual(payload["target"], "mobile")
        self.assertEqual(len(payload["components"]), 3)

    def test_duplicate_component_ids_are_rejected(self):
        page = PageDefinition(
            "p",
            "Page",
            components=(
                PageComponent("same", ComponentKind.TEXT),
                PageComponent("same", ComponentKind.TEXT, y=1),
            ),
        )
        with self.assertRaises(PageDefinitionError):
            page.validate()

    def test_executable_action_is_rejected(self):
        page = PageDefinition(
            "p",
            "Page",
            components=(PageComponent("x", ComponentKind.BUTTON, action="javascript:alert(1)"),),
        )
        with self.assertRaises(PageDefinitionError):
            page.validate()

    def test_component_cannot_overflow_grid(self):
        page = PageDefinition(
            "p",
            "Page",
            columns=4,
            components=(PageComponent("x", ComponentKind.TILE, x=3, width=2),),
        )
        with self.assertRaises(PageDefinitionError):
            page.validate()


if __name__ == "__main__":
    unittest.main()
