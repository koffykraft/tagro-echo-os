import unittest


class ClosingCashV03LiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = open("web/closing-cash-v03-live.html", encoding="utf-8").read()

    def test_preserves_standalone_and_adds_shared_queue(self):
        self.assertIn("closing-cash-v03.html", self.text)
        self.assertIn("runtime-config.js", self.text)
        self.assertIn("runtime-client.js", self.text)
        self.assertIn("/cash-days/save", self.text)
        self.assertIn("tagro.echo.cash-document-saved.v1", self.text)
        self.assertIn("enqueueAndFlush", self.text)

    def test_local_save_survives_sync_failure(self):
        self.assertIn("Saved locally · sync pending", self.text)
        self.assertIn("Saved locally · sign in to sync", self.text)
        self.assertIn("local_only_sync_error", self.text)

    def test_does_not_force_spreadsheet_yellow_column_into_expense_truth(self):
        self.assertIn("entries:[]", self.text)
        self.assertIn("document:rec", self.text)


if __name__ == "__main__":
    unittest.main()
