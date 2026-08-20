import unittest

from src.busy_dock.engine import (
    BusyDock,
    BusyDockError,
    BusyHandoffResult,
    BusyOperation,
    BusyRequest,
    BusySnapshot,
)
from src.enterprise.registry import BusyBinding, BusyNode, Enterprise, EnterpriseDirectory, EnterpriseUser
from src.repository.ports import MemoryRepository


class BusyDockTests(unittest.TestCase):
    def setUp(self):
        self.repo = MemoryRepository()
        self.directory = EnterpriseDirectory(self.repo)
        self.directory.register_enterprise(Enterprise("ent-kvr", "KVR", "Karavaloor Counter"))
        self.directory.register_enterprise(Enterprise("ent-pkm", "PKM", "Ponkunnam Counter"))
        self.directory.register_busy_node(BusyNode(
            "busy-main", "BUSY-MAIN", "ECHO Main BUSY", "COMP0013",
            capabilities=("masters_read","transactions_read","stock_read","balances_read","ledgers_read","reports_read"),
        ))
        self.directory.register_busy_node(BusyNode(
            "busy-alt", "BUSY-ALT", "ECHO Alternate BUSY", "COMP0020",
            capabilities=("masters_read","transactions_read","reports_read"),
        ))
        self.directory.bind_busy(BusyBinding(
            "bind-kvr", "ent-kvr", "busy-main", material_centre_ref="MC-KVR",
            voucher_series={"sale":"KVR-SALE"},
        ))
        self.directory.bind_busy(BusyBinding(
            "bind-pkm", "ent-pkm", "busy-alt", material_centre_ref="MC-PKM",
            voucher_series={"sale":"PKM-SALE"},
        ))
        self.dock = BusyDock(self.directory, self.repo)

    def test_routes_each_enterprise_to_its_busy_node(self):
        node, binding = self.dock.resolve("ent-kvr")
        self.assertEqual(node.busy_node_id, "busy-main")
        self.assertEqual(binding.material_centre_ref, "MC-KVR")
        node2, _ = self.dock.resolve("ent-pkm")
        self.assertEqual(node2.busy_node_id, "busy-alt")

    def test_offline_snapshot_is_explicitly_stale(self):
        self.dock.save_snapshot(BusySnapshot(
            "snap-1", "busy-main", "stock", [{"sku":"CS-3510","qty":3}],
            "2026-08-20T06:00:00+05:30", "2026-08-20T06:05:00+05:30",
            {"source":"normalized_busy_extract"},
        ))
        result = self.dock.read_offline(BusyRequest(
            "req-1", "ent-kvr", "user-1", BusyOperation.STOCK,
            idempotency_key="idem-1",
        ))
        self.assertEqual(result.status, "success")
        self.assertTrue(result.stale)
        self.assertEqual(result.source, "offline_snapshot")
        self.assertEqual(result.data[0]["qty"], 3)

    def test_missing_offline_snapshot_does_not_become_zero(self):
        result = self.dock.read_offline(BusyRequest(
            "req-2", "ent-kvr", "user-1", BusyOperation.BALANCES,
            idempotency_key="idem-2",
        ))
        self.assertEqual(result.status, "unavailable")
        self.assertIsNone(result.data)
        self.assertTrue(result.stale)

    def test_capability_is_enforced_per_node(self):
        with self.assertRaises(BusyDockError):
            self.dock.read_offline(BusyRequest(
                "req-3", "ent-pkm", "user-2", BusyOperation.STOCK,
                idempotency_key="idem-3",
            ))

    def test_handoff_envelope_is_idempotent_and_routed(self):
        req = BusyRequest(
            "req-4", "ent-kvr", "user-1", BusyOperation.REPORT,
            parameters={"report":"sales_register","date":"2026-08-20"},
            idempotency_key="idem-4",
        )
        first = self.dock.prepare_handoff(req)
        second = self.dock.prepare_handoff(req)
        self.assertEqual(first.envelope_id, second.envelope_id)
        self.assertEqual(first.busy_node_id, "busy-main")
        self.assertEqual(first.material_centre_ref, "MC-KVR")

    def test_idempotency_payload_change_is_rejected(self):
        self.dock.prepare_handoff(BusyRequest(
            "req-5", "ent-kvr", "user-1", BusyOperation.REPORT,
            parameters={"report":"sales_register"}, idempotency_key="idem-5",
        ))
        with self.assertRaises(BusyDockError):
            self.dock.prepare_handoff(BusyRequest(
                "req-5", "ent-kvr", "user-1", BusyOperation.REPORT,
                parameters={"report":"stock_status"}, idempotency_key="idem-5",
            ))

    def test_result_requires_known_envelope(self):
        with self.assertRaises(BusyDockError):
            self.dock.record_handoff_result(BusyHandoffResult(
                "unknown", "busy-main", "success", "2026-08-20T07:00:00+05:30"
            ))

    def test_multiple_users_share_same_counter_with_different_access(self):
        self.directory.register_user(EnterpriseUser(
            "assign-owner", "owner-1", "ent-kvr",
            roles=("franchisee_owner",), tool_packs=("sell","stock","cash","reports")
        ))
        self.directory.register_user(EnterpriseUser(
            "assign-staff", "staff-1", "ent-kvr",
            roles=("counter_staff",), tool_packs=("sell","service_accept","stock")
        ))
        self.directory.register_user(EnterpriseUser(
            "assign-exec", "exec-1", "ent-kvr",
            roles=("tagro_area_executive",), tool_packs=("reports","stock","attention")
        ))
        users = self.directory.users_for_enterprise("ent-kvr")
        self.assertEqual(len(users), 3)
        self.assertTrue(self.directory.user_has_tool("owner-1", "ent-kvr", "cash"))
        self.assertFalse(self.directory.user_has_tool("staff-1", "ent-kvr", "cash"))
        self.assertTrue(self.directory.user_has_role("exec-1", "ent-kvr", "tagro_area_executive"))
        self.assertEqual(self.directory.resolve_busy_binding("ent-kvr").material_centre_ref, "MC-KVR")


if __name__ == "__main__":
    unittest.main()
