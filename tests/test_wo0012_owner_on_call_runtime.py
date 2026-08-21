from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from src.aws_runtime.handler import lambda_handler
from src.aws_runtime.on_call_runtime import OnCallRuntimeError


class OwnerOnCallRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {
                "ECHO_ENV": "nonprod",
                "AWS_REGION": "ap-south-1",
                "DB_SECRET_ARN": "arn:test",
                "DB_HOST": "private",
                "DB_PORT": "5432",
                "DB_NAME": "echoos",
            },
            clear=False,
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()

    @staticmethod
    def event(query=None, subject="owner-1"):
        return {
            "rawPath": "/owner-on-call",
            "queryStringParameters": query or {},
            "requestContext": {
                "http": {"method": "GET"},
                "authorizer": {"jwt": {"claims": {"sub": subject}}},
            },
        }

    @patch("src.aws_runtime.handler.owner_on_call_readback")
    @patch("src.aws_runtime.handler.tenant_context")
    def test_owner_route_uses_server_side_owner_membership(self, context_mock, readback_mock):
        context_mock.return_value = {
            "principal_id": "principal-1",
            "enterprises": [
                {
                    "enterprise_id": "ent-tagro",
                    "role_code": "OWNER",
                    "capabilities": ["SELL"],
                }
            ],
        }
        readback_mock.return_value = {
            "schema": "tagro.echo.owner-on-call.v1",
            "projection_status": "not_accounting_final",
            "data": {
                "runtime_source": "echo_postgres_admitted_evidence",
                "historical_warehouse_included": False,
            },
        }
        response = lambda_handler(self.event({"start": "2026-08-01", "branch": "KVR"}), None)
        body = json.loads(response["body"])
        self.assertEqual(200, response["statusCode"])
        self.assertEqual("tagro.echo.owner-on-call.v1", body["schema"])
        readback_mock.assert_called_once_with(
            unittest.mock.ANY,
            enterprise_id="ent-tagro",
            start="2026-08-01",
            end=None,
            branch="KVR",
        )

    @patch("src.aws_runtime.handler.tenant_context")
    def test_non_owner_is_rejected(self, context_mock):
        context_mock.return_value = {
            "principal_id": "principal-1",
            "enterprises": [{"enterprise_id": "ent-tagro", "role_code": "STAFF", "capabilities": ["SELL"]}],
        }
        response = lambda_handler(self.event(), None)
        self.assertEqual(403, response["statusCode"])
        self.assertEqual("owner_authority_required", json.loads(response["body"])["error"])

    @patch("src.aws_runtime.handler.tenant_context")
    def test_multiple_owner_memberships_require_selection(self, context_mock):
        context_mock.return_value = {
            "principal_id": "principal-1",
            "enterprises": [
                {"enterprise_id": "ent-a", "role_code": "OWNER", "capabilities": []},
                {"enterprise_id": "ent-b", "role_code": "OWNER", "capabilities": []},
            ],
        }
        response = lambda_handler(self.event(), None)
        self.assertEqual(409, response["statusCode"])
        self.assertEqual("enterprise_selection_required", json.loads(response["body"])["error"])

    @patch("src.aws_runtime.handler.owner_on_call_readback")
    @patch("src.aws_runtime.handler.tenant_context")
    def test_invalid_query_is_not_silently_coerced(self, context_mock, readback_mock):
        context_mock.return_value = {
            "principal_id": "principal-1",
            "enterprises": [{"enterprise_id": "ent-tagro", "role_code": "OWNER", "capabilities": []}],
        }
        readback_mock.side_effect = OnCallRuntimeError("invalid start date")
        response = lambda_handler(self.event({"start": "not-a-date"}), None)
        self.assertEqual(400, response["statusCode"])
        self.assertEqual("invalid_on_call_query", json.loads(response["body"])["error"])

    def test_route_is_jwt_protected_in_sam(self):
        with open("architecture/aws/nonprod-runtime-template.yaml", encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("Path: /owner-on-call", text)
        block = text.split("OwnerOnCall:", 1)[1].split("BillingIssue:", 1)[0]
        self.assertNotIn("Authorizer: NONE", block)

    def test_runtime_projection_source_contract_is_explicit(self):
        with open("src/aws_runtime/on_call_runtime.py", encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn('"historical_warehouse_included"', text)
        self.assertIn("False", text)
        self.assertIn("external sealed/current warehouse coverage is not implied", text)
        self.assertIn("ExpenseRole.UNKNOWN", text)


if __name__ == "__main__":
    unittest.main()
