from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from src.aws_runtime.handler import lambda_handler


class Wo0012BillingRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = patch.dict(
            os.environ,
            {
                "ECHO_ENV": "nonprod",
                "AWS_REGION": "ap-south-1",
                "DB_SECRET_ARN": "arn:aws:secretsmanager:ap-south-1:272037674623:secret:test",
                "DB_HOST": "private.example.rds.amazonaws.com",
                "DB_PORT": "5432",
                "DB_NAME": "echoos",
            },
            clear=False,
        )
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()

    @staticmethod
    def event(payload, subject="staff-001"):
        return {
            "rawPath": "/billing/issue",
            "body": json.dumps(payload),
            "requestContext": {
                "http": {"method": "POST"},
                "authorizer": {"jwt": {"claims": {"sub": subject, "email": "staff@example.com"}}},
            },
        }

    def payload(self):
        return {
            "schema": "tagro.echo.billing-request.v1",
            "enterprise_id": "ent-tagro",
            "branch_code": "KVR",
            "customer_name": "Cash",
            "payment_mode": "cash",
            "idempotency_key": "device-1-bill-1",
            "lines": [
                {
                    "product_id": "prod-1",
                    "description": "MS 182",
                    "quantity": 1,
                    "unit_price_before_tax": 10000,
                    "gst_rate": 18,
                    "discount_before_tax": 0,
                }
            ],
        }

    @patch("src.aws_runtime.handler.issue_bill")
    @patch("src.aws_runtime.handler.tenant_context")
    def test_billing_uses_authenticated_server_membership_not_client_role(self, context_mock, issue_mock):
        context_mock.return_value = {
            "principal_id": "principal-1",
            "enterprises": [
                {
                    "membership_id": "mem-1",
                    "enterprise_id": "ent-tagro",
                    "role_code": "STAFF",
                    "capabilities": ["SELL"],
                }
            ],
        }
        issue_mock.return_value = {
            "bill_id": "echo-sale-1",
            "invoice_total": "11800.00",
            "busy_status": "not_booked_not_confirmed",
            "busy_series": None,
        }
        payload = self.payload()
        payload["actor_role"] = "OWNER"
        response = lambda_handler(self.event(payload), None)
        body = json.loads(response["body"])
        self.assertEqual(201, response["statusCode"])
        self.assertEqual("tagro.echo.bill-issued.v1", body["schema"])
        issue_mock.assert_called_once()
        self.assertEqual("STAFF", issue_mock.call_args.kwargs["membership"]["role_code"])

    @patch("src.aws_runtime.handler.tenant_context")
    def test_billing_requires_sell_capability(self, context_mock):
        context_mock.return_value = {
            "principal_id": "principal-1",
            "enterprises": [
                {
                    "membership_id": "mem-1",
                    "enterprise_id": "ent-tagro",
                    "role_code": "STAFF",
                    "capabilities": ["SERVICE"],
                }
            ],
        }
        response = lambda_handler(self.event(self.payload()), None)
        self.assertEqual(403, response["statusCode"])
        self.assertEqual("sell_capability_required", json.loads(response["body"])["error"])

    @patch("src.aws_runtime.handler.tenant_context")
    def test_multiple_memberships_require_explicit_enterprise_selection(self, context_mock):
        context_mock.return_value = {
            "principal_id": "principal-1",
            "enterprises": [
                {"enterprise_id": "ent-a", "role_code": "STAFF", "capabilities": ["SELL"]},
                {"enterprise_id": "ent-b", "role_code": "STAFF", "capabilities": ["SELL"]},
            ],
        }
        payload = self.payload()
        payload.pop("enterprise_id")
        response = lambda_handler(self.event(payload), None)
        self.assertEqual(409, response["statusCode"])
        self.assertEqual("enterprise_selection_required", json.loads(response["body"])["error"])

    def test_billing_route_is_not_public(self):
        event = self.event(self.payload())
        event["requestContext"].pop("authorizer")
        response = lambda_handler(event, None)
        self.assertEqual(401, response["statusCode"])

    def test_sam_declares_post_billing_issue_route(self):
        text = open("architecture/aws/nonprod-runtime-template.yaml", encoding="utf-8").read()
        self.assertIn("Path: /billing/issue", text)
        self.assertIn("Method: POST", text)
        # It inherits the JWT default authorizer; it must never be marked NONE.
        billing_block = text.split("BillingIssue:", 1)[1].split("ImportReconciliation:", 1)[0]
        self.assertNotIn("Authorizer: NONE", billing_block)


if __name__ == "__main__":
    unittest.main()
