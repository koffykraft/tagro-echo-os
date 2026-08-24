from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class BillingWebTests(unittest.TestCase):
    def test_billing_page_is_mobile_and_explicit_about_draft_truth(self):
        text = (ROOT / "web" / "billing.html").read_text(encoding="utf-8")
        self.assertIn('name="viewport"', text)
        self.assertIn("viewport-fit=cover", text)
        self.assertIn("LOCAL DRAFT", text)
        self.assertIn("Draft has not been issued", text)
        self.assertIn("WAITING TO SEND", text)
        self.assertIn("BUSY is not shown as booked until separate readback confirms it", text)

    def test_runtime_confirmation_required_before_issued_state(self):
        text = (ROOT / "web" / "billing.html").read_text(encoding="utf-8")
        self.assertIn("tagro.echo.bill-issued.v1", text)
        self.assertIn("EchoRuntime.enqueueAndFlush", text)
        self.assertIn("r.state==='acknowledged'", text)
        self.assertIn("r.response?.data?.bill_id", text)
        self.assertIn("ECHO ISSUED", text)
        self.assertIn("BUSY: not booked / not confirmed", text)

    def test_unknown_gst_remains_unknown_and_blocks_issue(self):
        text = (ROOT / "web" / "billing.html").read_text(encoding="utf-8")
        self.assertIn("gst_rate:v.gst_rate==null?null:Number(v.gst_rate)", text)
        self.assertIn("gst_known:Boolean(v.gst_known)", text)
        self.assertIn("GST incomplete for one or more selected products", text)
        self.assertIn("p.gst_known?'GST '+esc(p.gst_rate)+'%':'GST incomplete'", text)
        self.assertIn("unknown?'GST incomplete':money(t)", text)
        self.assertNotIn("gst_rate:Number(v.gst_rate??18)", text)
        self.assertNotIn("r.gst_rate=Number(p.gst_rate||0)", text)

    def test_billing_page_is_linked_and_cached(self):
        index = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        sw = (ROOT / "web" / "sw.js").read_text(encoding="utf-8")
        self.assertIn('href="billing.html"', index)
        self.assertIn("'./billing.html'", sw)


if __name__ == "__main__":
    unittest.main()
