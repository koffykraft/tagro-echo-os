import unittest

from src.aws_runtime.busy_round_trip import BusyRoundTripError, build_envelope


class BusyRoundTripContractTests(unittest.TestCase):
    def base(self, kind, normalized, **overrides):
        args = dict(
            enterprise_id="tagro",
            branch_id="kvr",
            record_kind=kind,
            operation="create",
            business_record_id="r1",
            normalized=normalized,
            busy_raw={"Tran1": {"VchCode": 1}},
            busy_unknown={},
            mapping_version="busy21-v1",
            mapping_validated=True,
            source_system="tagro-web",
            idempotency_key=f"{kind}-1",
        )
        args.update(overrides)
        return build_envelope(**args)

    def test_complete_sale_is_ready(self):
        result = self.base("sale", {
            "branch_code": "KVR", "voucher_date": "2026-08-27", "series": "Main",
            "party": "Cash", "lines": [{"item": "Chain", "quantity": 66, "rate": 12.5}],
        })
        self.assertEqual(result["write_status"], "ready")
        self.assertEqual(result["mapping_status"], "validated")

    def test_unknown_busy_fields_are_preserved_and_block_write(self):
        result = self.base(
            "purchase",
            {"branch_code": "KVR", "voucher_date": "2026-08-27", "series": "Main", "party": "Vendor", "lines": [{}]},
            busy_unknown={"Tran2.D17": "not decoded"},
        )
        self.assertEqual(result["busy_unknown"]["Tran2.D17"], "not decoded")
        self.assertEqual(result["write_status"], "blocked")

    def test_web_only_record_is_not_falsely_write_ready(self):
        result = self.base(
            "receipt",
            {"branch_code": "KVR", "voucher_date": "2026-08-27", "series": "Main", "account": "Cash", "amount": 100},
            busy_raw={},
        )
        self.assertEqual(result["write_status"], "blocked")
        self.assertIn("physical record is absent", result["uncertainty"])

    def test_all_required_kinds_have_contracts(self):
        examples = {
            "payment": {"branch_code": "KVR", "voucher_date": "2026-08-27", "series": "Main", "account": "Rent", "amount": 500},
            "item_master": {"name": "Nut M8", "alias": "9550801", "unit": "Pcs", "group": "Spares", "tax_category": "GST 18%", "hsn_code": "7318"},
            "account_master": {"name": "Cash", "alias": "", "group": "Cash-in-Hand"},
        }
        for kind, normalized in examples.items():
            with self.subTest(kind=kind):
                result = self.base(kind, normalized, idempotency_key=kind)
                self.assertEqual(result["record_kind"], kind)

    def test_unknown_kind_rejected(self):
        with self.assertRaises(BusyRoundTripError):
            self.base("estimate", {})


if __name__ == "__main__":
    unittest.main()
