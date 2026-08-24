from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
MANIFEST = WEB / "deploy-manifest.txt"


def admitted_paths() -> list[str]:
    return [
        line.strip()
        for line in MANIFEST.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


class WebReleaseIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admitted = admitted_paths()
        cls.admitted_set = set(cls.admitted)
        cls.html_paths = [path for path in cls.admitted if path.endswith(".html")]
        cls.html = {
            path: (WEB / path).read_text(encoding="utf-8")
            for path in cls.html_paths
        }

    def test_manifest_is_unique_and_every_file_exists(self):
        self.assertEqual(len(self.admitted), len(self.admitted_set))
        for relative in self.admitted:
            self.assertTrue((WEB / relative).is_file(), relative)

    def test_every_local_html_dependency_and_navigation_target_is_admitted(self):
        attr = re.compile(r"""(?:href|src)=["']([^"'#]+)["']""", re.I)
        for source, text in self.html.items():
            for raw in attr.findall(text):
                parsed = urlsplit(raw)
                if parsed.scheme or raw.startswith("//"):
                    continue
                target = parsed.path.lstrip("./")
                if not target or target == source:
                    continue
                self.assertIn(target, self.admitted_set, f"{source} -> {target}")

    def test_no_placeholder_or_missing_navigation_targets(self):
        combined = "\n".join(self.html.values())
        self.assertNotIn('href="#"', combined)
        self.assertNotIn("intelligence.html", combined)
        self.assertNotIn('href="styles.css"', combined)

    def test_login_is_a_keyboard_submittable_labeled_form(self):
        text = self.html["login.html"]
        self.assertIn('<form id="signInForm">', text)
        self.assertIn('type="submit"', text)
        for field in ("email", "password", "newPassword", "enterprise"):
            self.assertIn(f'for="{field}"', text)
            self.assertIn(f'id="{field}"', text)
            self.assertIn(f'name="{field}"', text)
        self.assertIn("form.addEventListener('submit'", text)
        self.assertIn('aria-live="polite"', text)

    def test_release_uses_only_owner_approved_brand_lockups(self):
        compact = "assets/brand/tagro-stihl-900x240.png"
        wide = "assets/brand/tagro-stihl-1600x400.png"
        self.assertIn(compact, self.admitted_set)
        self.assertIn(wide, self.admitted_set)
        combined = "\n".join(self.html.values())
        self.assertNotIn("tagro-stihl-mobile.png", combined)
        self.assertNotIn("tagro-stihl-desktop.png", combined)
        for source, text in self.html.items():
            self.assertIn(compact, text, source)

    def test_owner_approved_brand_bytes_are_exact(self):
        expected = {
            "assets/brand/tagro-stihl-900x240.png": "7051aaaa6ce2a811e635385ee9d231a1e96bd1455eddd9022a56d85d16777b50",
            "assets/brand/tagro-stihl-1600x400.png": "60013d9cdafcb1461af8909be2552a4f8d924d7f318c5d28c473ced22aa80bd3",
        }
        for relative, digest in expected.items():
            self.assertEqual(hashlib.sha256((WEB / relative).read_bytes()).hexdigest(), digest)

    def test_service_worker_caches_both_current_brand_assets(self):
        worker = (WEB / "sw.js").read_text(encoding="utf-8")
        self.assertIn("tagro-stihl-os-v13", worker)
        self.assertEqual(worker.count("assets/brand/tagro-stihl-900x240.png"), 1)
        self.assertEqual(worker.count("assets/brand/tagro-stihl-1600x400.png"), 1)
        self.assertNotIn("tagro-stihl-mobile.png", worker)
        self.assertNotIn("tagro-stihl-desktop.png", worker)

if __name__ == "__main__":
    unittest.main()
