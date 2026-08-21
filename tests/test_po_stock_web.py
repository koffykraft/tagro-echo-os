from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PoStockWebTests(unittest.TestCase):
    def test_po_draft_does_not_claim_supplier_order(self):
        text = (ROOT / "web" / "po.html").read_text(encoding="utf-8")
        self.assertIn("awaiting_owner_approval", text)
        self.assertIn("supplier_order_sent:false", text)
        self.assertIn("nothing has been sent to the supplier", text)

    def test_stock_count_evidence_does_not_mutate_stock(self):
        text = (ROOT / "web" / "stock-count.html").read_text(encoding="utf-8")
        self.assertIn("stock_mutated:false", text)
        self.assertIn("Stock has not been changed", text)
        self.assertIn("variance", text)

    def test_stock_count_uses_authenticated_queue_and_real_reference_data(self):
        text = (ROOT / "web" / "stock-count.html").read_text(encoding="utf-8")
        self.assertIn("runtime-config.js", text)
        self.assertIn("runtime-client.js", text)
        self.assertIn("EchoRuntime.enqueueAndFlush", text)
        self.assertIn("EchoRuntime.reference('branches'", text)
        self.assertIn("EchoRuntime.reference('products'", text)
        self.assertNotIn("credentials:'include'", text)
        self.assertNotIn("fetch('/stock-count/record'", text)

    def test_stock_count_keeps_recounts_and_unknown_canonical_truth(self):
        text = (ROOT / "web" / "stock-count.html").read_text(encoding="utf-8")
        self.assertIn("db.rows.push(row)", text)
        self.assertNotIn("db.rows=db.rows.filter", text)
        self.assertIn("canonical movement quantity is unknown, not zero", text)
        self.assertIn("observation_id", text)
        self.assertIn("EchoRuntime.acknowledgement", text)

    def test_pages_are_linked_and_cached(self):
        index = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        sw = (ROOT / "web" / "sw.js").read_text(encoding="utf-8")
        for page in ("po.html", "stock-count.html"):
            self.assertIn(f'href="{page}"', index)
            self.assertIn(f"'./{page}'", sw)


if __name__ == "__main__":
    unittest.main()
