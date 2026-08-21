from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "web" / "closing-cash-v03.html"


class ClosingCashV03TrialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = PAGE.read_text(encoding="utf-8")

    def test_dual_render_and_context(self):
        for marker in ('class="desktop"', 'class="mobile"', 'id="businessDate"', 'id="branch"', 'id="enteredBy"', 'id="switchReason"'):
            self.assertIn(marker, self.text)
        self.assertIn("Reason for entering for another branch/person", self.text)

    def test_single_line_mobile_navigation(self):
        self.assertNotIn("contenteditable", self.text)
        self.assertIn('enterkeyhint="next"', self.text)
        self.assertIn("moveSameColumn", self.text)
        self.assertIn("if(e.key==='Enter')", self.text)

    def test_excel_formula_chain_is_preserved(self):
        self.assertIn("total=money(yesterday+sales)", self.text)
        self.assertIn("balance=money(total-expenses)", self.text)
        self.assertIn("difference=money(cash-balance)", self.text)

    def test_review_save_and_standalone_database(self):
        self.assertIn("Review Closing Cash", self.text)
        self.assertIn("Confirm Save", self.text)
        self.assertIn("indexedDB.open('tagro-cc-standalone'", self.text)
        self.assertIn("closing_cash", self.text)
        self.assertIn("images", self.text)
        self.assertIn("status:'confirmed_local'", self.text)
        self.assertIn("shared_runtime_state:'not_yet_connected'", self.text)

    def test_export_and_share_controls_exist(self):
        for marker in ("Share Image", "Save Image", "PDF / Print", 'id="sendMe" checked', 'id="sendOwner" checked', "recordImage", "window.print"):
            self.assertIn(marker, self.text)

    def test_presentation_colours_are_metadata_not_financial_semantics(self):
        self.assertIn("styles:seed.styles||{}", self.text)
        self.assertIn("applyStyle", self.text)
        self.assertIn("Cell highlight", self.text)


if __name__ == "__main__":
    unittest.main()
