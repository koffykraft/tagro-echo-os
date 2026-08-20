from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts/core/PAGE_ECOLOGY_CONTRACT.json"


class Wo0012PageEcologyContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.text = CONTRACT.read_text(encoding="utf-8").lower()

    def test_page_is_operational_projection_not_merely_html(self) -> None:
        self.assertIn("operational projection", self.text)
        self.assertIn("not merely html", self.text)

    def test_inherited_page_assets_are_candidates_not_design_authority(self) -> None:
        inherited = self.contract["inherited_asset_rule"]
        self.assertEqual(inherited["status"], "candidate_only")
        for kind in ("page_design", "label", "copy_text", "data_binding", "navigation_connection"):
            self.assertIn(kind, inherited["candidate_kinds"])

    def test_presence_and_absence_are_both_governed(self) -> None:
        self.assertIn("presence does not create relevance", self.text)
        self.assertIn("absence can be consequential", self.text)
        self.assertIn("required absence is observable state", self.text)

    def test_everything_requires_planar_placement(self) -> None:
        placement = self.contract["placement_rule"]
        self.assertIn("a place for everything", placement["principle"])
        for check in (
            "correct_page",
            "correct_region",
            "correct_sequence",
            "correct_visibility",
            "correct_data_connection",
            "correct_event_connection",
            "correct_failure_path",
        ):
            self.assertIn(check, placement["required_checks"])

    def test_page_receivers_obey_spectral_relevance(self) -> None:
        spectral = self.contract["spectral_rule"]
        self.assertEqual(spectral["non_match"], "semantically_inert")
        self.assertIn("must not change label", spectral["effect"])
        self.assertIn("user attention", spectral["effect"])

    def test_static_pollution_has_named_classes_and_retirement(self) -> None:
        pollution = self.contract["pollution_rule"]
        for static_class in (
            "orphan_control",
            "stale_label",
            "duplicate_truth",
            "dead_navigation",
            "hidden_required_context",
            "environment_mismatch",
            "stale_projection",
        ):
            self.assertIn(static_class, pollution["static_classes"])
        self.assertIn("retire", pollution["actions"])

    def test_acceptance_requires_environment_and_failure_behavior(self) -> None:
        must_prove = self.contract["acceptance"]["must_prove"]
        self.assertIn("environment behavior", must_prove)
        self.assertIn("failure/recovery behavior", must_prove)
        self.assertIn("usable wording and labels", must_prove)
        self.assertIn("correct data/event binding", must_prove)


if __name__ == "__main__":
    unittest.main()
