import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


class MobileReadinessTests(unittest.TestCase):
    pages = [
        "index.html", "login.html", "on-call.html", "billing.html", "service.html", "customers.html", "po.html",
        "stock-count.html", "closing-cash.html", "business.html",
    ]
    retained_utilities = ["reports.html", "page-builder.html", "counter.html", "cash.html", "bank.html", "payments.html", "documents.html"]

    def test_required_mobile_pages_exist_and_have_viewport(self):
        for name in self.pages + self.retained_utilities:
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

    def test_service_worker_caches_canonical_static_shell_but_never_generic_api_gets(self):
        sw = (WEB / "sw.js").read_text(encoding="utf-8")
        for name in self.pages:
            self.assertIn(f"./{name}", sw)
        self.assertIn("runtime-config.js", sw)
        self.assertIn("runtime-client.js", sw)
        self.assertIn("url.origin!==self.location.origin", sw)
        self.assertIn("STATIC_URLS.has(request.url)", sw)
        self.assertNotIn("caches.put(event.request", sw)
        self.assertNotIn("./intelligence.html", sw)
        # Retained builder/admin utilities are not forced into every counter's offline shell.
        self.assertNotIn("'./page-builder.html'", sw)

    def test_index_registers_service_worker_and_projects_network_state(self):
        index = (WEB / "index.html").read_text(encoding="utf-8")
        home_js = (WEB / "echo-home-v1.js").read_text(encoding="utf-8")
        self.assertIn("manifest.webmanifest", index)
        self.assertIn("serviceWorker.register('./sw.js')", index)
        self.assertIn('id="networkLabel"', index)
        self.assertIn("navigator.onLine", home_js)
        self.assertIn("'Online':'Offline'", home_js)
        self.assertIn("Waiting to send", index)
        self.assertIn('href="on-call.html"', index)
        self.assertNotIn('href="intelligence.html"', index)

    def test_current_tagro_vertical_uses_owner_approved_stihl_brand_assets(self):
        compact = "assets/brand/tagro-stihl-900x240.png"
        wide = "assets/brand/tagro-stihl-1600x400.png"
        for asset in (compact, wide):
            self.assertTrue((WEB / asset).is_file(), asset)
        for name in self.pages:
            text = (WEB / name).read_text(encoding="utf-8")
            self.assertIn("TAGRO STIHL", text, name)
            self.assertIn(compact, text, name)
            self.assertIn(wide, text, name)
            self.assertNotIn("tagro-stihl-mobile.png", text, name)
            self.assertNotIn("tagro-stihl-desktop.png", text, name)
        manifest = json.loads((WEB / "manifest.webmanifest").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "TAGRO STIHL")
        self.assertEqual(manifest["short_name"], "TAGRO STIHL")
        sw = (WEB / "sw.js").read_text(encoding="utf-8")
        self.assertIn(compact, sw)
        self.assertIn(wide, sw)
        self.assertIn("tagro-stihl-os", sw)

    def test_runtime_client_uses_bearer_jwt_and_scoped_offline_queue(self):
        text = (WEB / "runtime-client.js").read_text(encoding="utf-8")
        self.assertIn("authorization:`Bearer ${s.idToken}`", text)
        self.assertIn("sessionStorage", text)
        self.assertIn("principal", text.lower())
        self.assertIn("enterpriseId", text)
        self.assertIn("deviceId", text)
        self.assertIn("enqueueMutation", text)
        self.assertIn("flushQueue", text)
        self.assertIn("idempotency", text.lower())
        self.assertNotIn("PASSWORD:String(password)", (WEB / "runtime-config.js").read_text(encoding="utf-8"))

    def test_login_does_not_store_password(self):
        text = (WEB / "login.html").read_text(encoding="utf-8")
        self.assertIn("runtime-client.js", text)
        self.assertIn("EchoRuntime.login", text)
        self.assertNotIn("localStorage.setItem('password", text)
        self.assertNotIn("sessionStorage.setItem('password", text)

    def test_owner_on_call_refuses_to_invent_missing_runtime_data(self):
        text = (WEB / "on-call.html").read_text(encoding="utf-8")
        self.assertIn("/owner-on-call", text)
        self.assertIn("No financial value has been invented or substituted.", text)
        self.assertIn("not accounting final", text)
        self.assertNotIn("demo", text.lower())


if __name__ == "__main__":
    unittest.main()
