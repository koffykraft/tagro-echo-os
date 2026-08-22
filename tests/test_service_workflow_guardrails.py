from __future__ import annotations

import unittest

from src.service.service import MachineRecord, ServiceStore


class ServiceWorkflowGuardrailTests(unittest.TestCase):
    def setUp(self):
        self.store = ServiceStore()
        self.store.add_machine(MachineRecord("mach-1", "cus-1", "prd-1", "MS 382", "SER-1"))

    def test_job_requires_machine_customer_consistency(self):
        with self.assertRaisesRegex(ValueError, "does not own"):
            self.store.open_job("KVR", "cus-2", "mach-1", "Stops when hot", "usr-1")

    def test_normal_status_flow_is_constrained(self):
        job = self.store.open_job("KVR", "cus-1", "mach-1", "Stops when hot", "usr-1")
        with self.assertRaisesRegex(ValueError, "invalid service transition"):
            self.store.update_status(job.job_id, "delivered", "Skip work", "usr-2")
        job = self.store.update_status(job.job_id, "inspecting", "Diagnosis started", "usr-2")
        job = self.store.update_status(job.job_id, "repairing", "Minor repair; approval not required", "usr-2")
        job = self.store.update_status(job.job_id, "ready", "Bench test passed", "usr-2")
        job = self.store.update_status(job.job_id, "delivered", "Collected", "usr-1")
        self.assertEqual(job.status, "delivered")

    def test_owner_override_is_explicit_evidence(self):
        job = self.store.open_job("KVR", "cus-1", "mach-1", "Inspection only", "usr-1")
        job = self.store.update_status(
            job.job_id,
            "ready",
            "Owner directs return without repair",
            "owner-1",
            owner_override=True,
        )
        self.assertEqual(job.status, "ready")
        override_events = [e for e in self.store.events if e.event_type == "owner_override.status"]
        self.assertEqual(len(override_events), 1)
        self.assertIn("received -> ready", override_events[0].note)

    def test_observations_do_not_change_status(self):
        job = self.store.open_job("KVR", "cus-1", "mach-1", "No start", "usr-1")
        self.store.add_observation(job.job_id, "Fuel is old", "usr-2")
        self.assertEqual(self.store.jobs[job.job_id].status, "received")


if __name__ == "__main__":
    unittest.main()
