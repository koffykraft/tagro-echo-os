from __future__ import annotations

import inspect
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from src.core.event import (
    ActorRef,
    AuthorityContext,
    ConfidenceContext,
    EntityRef,
    EventEnvelope,
    EvidenceRef,
    LocationRef,
)
from src.driver.ports import Command
from src.observer import ports as observer_ports


class RuntimeSkeletonTests(unittest.TestCase):
    def make_event(self) -> EventEnvelope:
        now = datetime.now(timezone.utc)
        return EventEnvelope(
            event_id="evt-001",
            event_type="stock.observation.confirmed",
            schema_version="1.0",
            event_time=now,
            recorded_time=now,
            source_effective_time=now,
            actor=ActorRef(actor_type="staff", actor_id="staff-001"),
            location=LocationRef(location_type="counter", location_id="counter-001"),
            authority=AuthorityContext(
                authority_scope=("stock.observe",),
                authenticated=True,
                authority_source="session",
            ),
            entities=(EntityRef("sku", "sku-001", "observed"),),
            evidence=(EvidenceRef("evidence-001", "photo", "counter-mobile", 0.96),),
            provenance={"source": "counter-mobile"},
            confidence=ConfidenceContext(score=1.0, status="confirmed", basis="staff confirmation"),
            idempotency_key="counter-001:stock-count:evt-001",
            payload={"quantity": 3},
        )

    def test_event_validates(self) -> None:
        self.make_event().validate()

    def test_runtime_event_serializes_to_canonical_schema_shape(self) -> None:
        payload = self.make_event().to_dict()
        schema = json.loads(Path("schemas/core/EVENT_ENVELOPE.schema.json").read_text(encoding="utf-8"))
        self.assertTrue(set(schema["required"]).issubset(payload.keys()))
        self.assertEqual(set(payload.keys()), set(schema["properties"].keys()))
        self.assertIsInstance(payload["actor"], dict)
        self.assertIsInstance(payload["location"], dict)
        self.assertIsInstance(payload["authority"], dict)
        self.assertIsInstance(payload["confidence"], dict)
        self.assertIsInstance(payload["caused_by"], list)
        self.assertIsInstance(payload["supersedes"], list)

    def test_driver_command_requires_idempotency_key(self) -> None:
        command = Command(
            command_id="cmd-001",
            command_type="sale.create",
            idempotency_key="",
            actor_id="staff-001",
            authority_scope=("sale.create",),
            payload={},
        )
        with self.assertRaises(ValueError):
            command.validate()

    def test_observer_interface_has_no_driver_execution_method(self) -> None:
        names = {name for name, _ in inspect.getmembers(observer_ports.ObserverPort)}
        self.assertIn("observe", names)
        self.assertNotIn("execute", names)

    def test_observer_module_does_not_import_driver(self) -> None:
        source = inspect.getsource(observer_ports)
        self.assertNotIn("src.driver", source)


if __name__ == "__main__":
    unittest.main()
