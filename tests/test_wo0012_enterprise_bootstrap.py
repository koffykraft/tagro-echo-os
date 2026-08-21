from __future__ import annotations

import unittest
from pathlib import Path

from src.aws_runtime.bootstrap import CONFIRMATION, validate_request

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "architecture/aws/nonprod-runtime-template.yaml"
MAKEFILE = ROOT / "Makefile"
BOOTSTRAP = ROOT / "src/aws_runtime/bootstrap.py"


class Wo0012EnterpriseBootstrapTests(unittest.TestCase):
    def test_bootstrap_requires_exact_nonprod_confirmation(self) -> None:
        self.assertEqual("BOOTSTRAP_NONPROD_ENTERPRISE_V0_1", CONFIRMATION)
        with self.assertRaisesRegex(ValueError, "explicit_confirmation_required"):
            validate_request({})

    def test_bootstrap_validates_required_identity_and_capabilities(self) -> None:
        request = validate_request(
            {
                "confirm": CONFIRMATION,
                "enterprise_code": "tagro",
                "enterprise_name": "TAGRO",
                "owner_external_identity_ref": "cognito-sub",
                "owner_display_name": "Owner",
                "owner_email": "owner@example.com",
                "capabilities": ["sell", "service", "sell"],
            }
        )
        self.assertEqual("TAGRO", request.enterprise_code)
        self.assertEqual(("SELL", "SERVICE"), request.capabilities)
        self.assertEqual("owner@example.com", request.owner_email)

    def test_owner_email_is_optional_but_never_invented(self) -> None:
        request = validate_request(
            {
                "confirm": CONFIRMATION,
                "enterprise_code": "tagro",
                "enterprise_name": "TAGRO",
                "owner_external_identity_ref": "cognito-sub",
                "owner_display_name": "Owner",
                "capabilities": ["sell"],
            }
        )
        self.assertIsNone(request.owner_email)
        source = BOOTSTRAP.read_text(encoding="utf-8")
        self.assertIn("if request.owner_email and user_id", source)
        self.assertIn("never invent an email", source.lower())

    def test_invalid_owner_email_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid_owner_email"):
            validate_request(
                {
                    "confirm": CONFIRMATION,
                    "enterprise_code": "tagro",
                    "enterprise_name": "TAGRO",
                    "owner_external_identity_ref": "cognito-sub",
                    "owner_email": "not-an-email",
                    "capabilities": ["sell"],
                }
            )

    def test_bootstrap_is_idempotent_and_nonprod_only(self) -> None:
        source = BOOTSTRAP.read_text(encoding="utf-8").lower()
        self.assertIn('config.environment != "nonprod"', source)
        self.assertGreaterEqual(source.count("on conflict"), 5)
        self.assertNotIn("delete from", source)
        self.assertNotIn("drop table", source)

    def test_owner_runtime_user_is_explicit_and_branch_unassigned(self) -> None:
        source = BOOTSTRAP.read_text(encoding="utf-8")
        self.assertIn("insert into users", source)
        self.assertIn("'OWNER', null, true", source)
        self.assertIn('"user_id": user_id', source)

    def test_bootstrap_lambda_has_no_public_or_scheduled_event_source(self) -> None:
        template = TEMPLATE.read_text(encoding="utf-8")
        start = template.index("  EchoEnterpriseBootstrapFunction:")
        end = template.index("\nOutputs:", start)
        block = template[start:end]
        self.assertIn("echo-nonprod-enterprise-bootstrap", block)
        self.assertNotIn("Events:", block)
        self.assertNotIn("Type: HttpApi", block)
        self.assertIn("VpcConfig:", block)

    def test_build_packages_bootstrap_function(self) -> None:
        makefile = MAKEFILE.read_text(encoding="utf-8")
        self.assertIn("build-EchoEnterpriseBootstrapFunction:", makefile)
        self.assertIn("build_echo_python_function", makefile)

    def test_tenant_context_route_remains_jwt_protected(self) -> None:
        template = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("Path: /tenant-context", template)
        tenant_route = template[template.index("        TenantContext:"):template.index("\n\n  EchoSchemaMigrationFunction:")]
        self.assertNotIn("Authorizer: NONE", tenant_route)


if __name__ == "__main__":
    unittest.main()
