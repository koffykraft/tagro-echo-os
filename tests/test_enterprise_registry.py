import unittest

from src.enterprise import (
    BusyBinding,
    BusyNode,
    Enterprise,
    EnterpriseDirectory,
    EnterpriseUser,
    RegistryError,
)
from src.repository.ports import MemoryRepository


class EnterpriseDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.registry = EnterpriseDirectory(MemoryRepository())

    def test_hierarchy_is_configurable_and_identity_is_stable(self):
        self.registry.register_enterprise(Enterprise("ent-network", "ECHO", "TAGRO ECHO", "network"))
        self.registry.register_enterprise(Enterprise("ent-region", "SOUTH", "South Region", "region", "ent-network"))
        self.registry.register_enterprise(Enterprise("ent-counter", "PNR01", "Punalur Counter", "counter", "ent-region"))

        counter = self.registry.get_enterprise("ent-counter")
        self.assertEqual(counter.code, "PNR01")
        self.assertEqual([x.enterprise_id for x in self.registry.ancestors_of("ent-counter")], ["ent-region", "ent-network"])
        self.assertEqual([x.enterprise_id for x in self.registry.children_of("ent-region")], ["ent-counter"])

    def test_hierarchy_cycle_is_rejected(self):
        self.registry.register_enterprise(Enterprise("a", "A", "A", "region"))
        self.registry.register_enterprise(Enterprise("b", "B", "B", "counter", "a"))
        with self.assertRaises(RegistryError):
            self.registry.register_enterprise(Enterprise("a", "A", "A", "region", "b"))

    def test_duplicate_enterprise_code_is_rejected_case_insensitively(self):
        self.registry.register_enterprise(Enterprise("a", "KLM01", "Counter A"))
        with self.assertRaises(RegistryError):
            self.registry.register_enterprise(Enterprise("b", "klm01", "Counter B"))

    def test_user_assignment_keeps_tool_packs_and_roles(self):
        self.registry.register_enterprise(Enterprise("e1", "E1", "Counter One"))
        self.registry.register_user(EnterpriseUser("ua1", "u1", "e1", ("counter_operator",), ("sell", "service", "closing_cash")))
        user = self.registry.users_for_enterprise("e1")[0]
        self.assertEqual(user.user_id, "u1")
        self.assertIn("service", user.tool_packs)

    def test_one_busy_node_can_serve_multiple_enterprises_as_material_centres(self):
        self.registry.register_enterprise(Enterprise("e1", "E1", "Counter One"))
        self.registry.register_enterprise(Enterprise("e2", "E2", "Counter Two"))
        self.registry.register_busy_node(BusyNode("busy-main", "BUSY-HO", "ECHO Main BUSY", "COMP0001"))
        self.registry.bind_busy(BusyBinding("b1", "e1", "busy-main", material_centre_ref="MC-E1", voucher_series={"sale":"E1-SALES"}))
        self.registry.bind_busy(BusyBinding("b2", "e2", "busy-main", material_centre_ref="MC-E2", voucher_series={"sale":"E2-SALES"}))

        enterprises = self.registry.enterprises_for_busy_node("busy-main")
        self.assertEqual({e.enterprise_id for e in enterprises}, {"e1", "e2"})
        self.assertEqual(self.registry.resolve_busy_binding("e1").material_centre_ref, "MC-E1")

    def test_multiple_busy_companies_can_coexist(self):
        self.registry.register_enterprise(Enterprise("group", "GROUP", "Large Operator", "operator"))
        self.registry.register_busy_node(BusyNode("busy-a", "BUSY-A", "Company A", "COMP0007"))
        self.registry.register_busy_node(BusyNode("busy-b", "BUSY-B", "Company B", "COMP0012"))
        self.registry.bind_busy(BusyBinding("ba", "group", "busy-a", "primary_accounts"))
        self.registry.bind_busy(BusyBinding("bb", "group", "busy-b", "secondary_company"))

        bindings = self.registry.busy_bindings_for_enterprise("group")
        self.assertEqual({b.busy_node_id for b in bindings}, {"busy-a", "busy-b"})

    def test_same_enterprise_cannot_have_two_active_bindings_for_same_role(self):
        self.registry.register_enterprise(Enterprise("e1", "E1", "Counter One"))
        self.registry.register_busy_node(BusyNode("busy-a", "A", "A", "COMP0001"))
        self.registry.register_busy_node(BusyNode("busy-b", "B", "B", "COMP0002"))
        self.registry.bind_busy(BusyBinding("ba", "e1", "busy-a", "primary_accounts"))
        with self.assertRaises(RegistryError):
            self.registry.bind_busy(BusyBinding("bb", "e1", "busy-b", "primary_accounts"))

    def test_unknown_enterprise_or_busy_node_cannot_be_bound(self):
        self.registry.register_enterprise(Enterprise("e1", "E1", "Counter One"))
        with self.assertRaises(RegistryError):
            self.registry.bind_busy(BusyBinding("b1", "e1", "missing"))
        self.registry.register_busy_node(BusyNode("busy", "B", "Busy", "COMP0001"))
        with self.assertRaises(RegistryError):
            self.registry.bind_busy(BusyBinding("b2", "missing", "busy"))


if __name__ == "__main__":
    unittest.main()
