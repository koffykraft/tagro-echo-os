from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts/core/VIBGYOR_PRISM_CONTRACT.json"
SCALE_MAP = ROOT / "docs/FUTURE_SCALE_MAP.md"


class Wo0012VibgyorContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.invariants = " ".join(cls.contract["invariants"]).lower()
        cls.scale_map = SCALE_MAP.read_text(encoding="utf-8").lower()

    def test_all_seven_spectral_bands_are_declared_once(self) -> None:
        self.assertEqual([band["code"] for band in self.contract["bands"]], list("VIBGYOR"))
        self.assertTrue(all(band["semantic_scope"] == "contract_defined" for band in self.contract["bands"]))

    def test_prism_does_not_create_duplicate_truth(self) -> None:
        self.assertIn("originating event remains whole and unchanged", self.invariants)
        self.assertIn("retain originating event identity and provenance", self.invariants)

    def test_nonmatching_receiver_is_semantically_inert(self) -> None:
        self.assertIn("non-matching projection is semantically inert", self.invariants)
        self.assertIn("presence at a receiver never creates a chord", self.invariants)

    def test_colour_is_not_strength_or_authority(self) -> None:
        self.assertIn("spectral band and vector strength are independent", self.invariants)
        self.assertIn("does not replace evidence, authority, timing", self.invariants)

    def test_phased_tagro_move_is_part_of_scale_map(self) -> None:
        self.assertIn("tagro phased move-house validation", self.scale_map)
        self.assertIn("matching/non-matching receivers", self.scale_map)
        self.assertIn("empirical test of the planar/vibgyor model", self.scale_map)


if __name__ == "__main__":
    unittest.main()
