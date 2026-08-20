import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


class MobileReadinessTests(unittest.TestCase):
    pages = ["index.html","counter.html","service.html","cash.html","bank.html","payments.html","documents.html"]

    def test_required_mobile_pages_exist_and_have_viewport(self):
        for name in self.pages:
            p = WEB / name
            self.assertTrue(p.exists(), name)
            text = p.read_text(encoding="utf-8")
            self.assertIn('name="viewport"', text, name)

    def test_core_pages_do_not_depend_on_external_cdn(self):
        for name in self.pages:
            text = (WEB / name).read_text(encoding="utf-8")
            self.assertNotIn("cdn.", text.lower(), name)
            self.assertNotIn("unpkg.com", text.lower(), name)
            self.assertNotIn("jsdelivr.net", text.lower(), name)

    def test_manifest_is_local_standalone_candidate(self):
        manifest = json.loads((WEB / "manifest.webmanifest").read_text(encoding="utf-8"))
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["start_url"], "./index.html")
        self.assertTrue(manifest["icons"])
        for icon in manifest["icons"]:
            self.assertFalse(icon["src"].startswith("http"))

    def test_service_worker_caches_all_core_pages(self):
        sw = (WEB / "sw.js").read_text(encoding="utf-8")
        for name in self.pages:
            self.assertIn(f"./{name}", sw)
        self.assertIn("caches.open", sw)
        self.assertIn("fetch(event.request)", sw)
        self.assertIn("caches.match", sw)

    def test_index_registers_service_worker_and_labels_network_state(self):
        text = (WEB / "index.html").read_text(encoding="utf-8")
        self.assertIn("manifest.webmanifest", text)
        self.assertIn("serviceWorker.register('./sw.js')", text)
        self.assertIn("OFFLINE", text)
        self.assertIn("ONLINE", text)
        self.assertIn("Pending local work", text)


if __name__ == "__main__":
    unittest.main()
