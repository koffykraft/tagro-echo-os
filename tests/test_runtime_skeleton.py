from __future__ import annotations

import inspect
import unittest
from datetime import datetime, timezone

from src.core.event import AuthorityContext, EntityRef, EventEnvelope, EvidenceRef
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
            location_id="counter-001",
            authority=AuthorityContext(
                actor_id="staff-001",
                actor_type="staff",
                authority_scope=("stock.observe",),
                authenticated=True,
            ),
            entities=(EntityRef("sku", "sku-001", "observed"),),
            evidence=(EvidenceRef("evidence-001", "photo", "counter-mobile", 0.96),),
            provenance={"source": "counter-mobile"},
            confidence=1.0,
            idempotency_key="counter-001:stock-count:evt-001",
            payload={"quantity": 3},
        )

    def test_event_validates(self) -> None:
        self.make_event().validate()

    def test_event_requires_idempotency_key(self) -> None:
        event = self.make_event()
        broken = EventEnvelope(**{**event.__dict__, "idempotency_key": ""})
        with self.assertRaises(ValueError):
            broken.validate()

    def test_consequential_event_requires_authenticated_authority(self) -> None:
        event = self.make_event()
        authority = AuthorityContext(
            actor_id="staff-001",
            actor_type="staff",
            authority_scope=("stock.observe",),
            authenticated=False,
        )
        broken = EventEnvelope(**{**event.__dict__, "authority": authority})
        with self.assertRaises(ValueError):
            broken.validate()

    def test_observer_interface_has_no_driver_execution_method(self) -> None:
        names = {name for name, _ in inspect.getmembers(observer_ports.ObserverPort)}
        self.assertIn("observe", names)
        self.assertNotIn("execute", names)

    def test_observer_module_does_not_import_driver(self) -> None:
        source = inspect.getsource(observer_ports)
        self.assertNotIn("src.driver", source)


if __name__ == "__main__":
    unittest.main()
