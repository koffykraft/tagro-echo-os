from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from src.aws_runtime.handler import lambda_handler


class CustomerCreateRouteTests(unittest.TestCase):
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
    def event(payload):
        return {
            "rawPath": "/customers",
            "body": json.dumps(payload),
            "requestContext": {
                "http": {"method": "POST"},
                "authorizer": {"jwt": {"claims": {"sub": "staff-1"}}},
            },
        }

    @staticmethod
    def context(capabilities):
        return {
            "principal_id": "principal-1",
            "enterprises": [
                {
                    "membership_id": "mem-1",
                    "enterprise_id": "ent-tagro",
                    "role_code": "STAFF",
                    "capabilities": capabilities,
                }
            ],
        }

    @patch("src.aws_runtime.handler.create_customer")
    @patch("src.aws_runtime.handler.tenant_context")
    def test_sell_or_service_staff_can_create_customer(self, context_mock, operation_mock):
        for capability in ("SELL", "SERVICE"):
            with self.subTest(capability=capability):
                context_mock.return_value = self.context([capability])
                operation_mock.return_value = {
                    "customer_id": "customer-1",
                    "name": "Customer",
                    "phone": "9999999999",
                    "matched_existing": False,
                    "idempotent_replay": False,
                }
                response = lambda_handler(
                    self.event(
                        {
                            "enterprise_id": "ent-tagro",
                            "name": "Customer",
                            "phone": "9999999999",
                            "idempotency_key": "customer-command-1",
                        }
                    ),
                    None,
                )
                body = json.loads(response["body"])
                self.assertEqual(201, response["statusCode"])
                self.assertEqual("tagro.echo.customer-created.v1", body["schema"])

    @patch("src.aws_runtime.handler.tenant_context")
    def test_unrelated_capability_is_rejected(self, context_mock):
        context_mock.return_value = self.context(["STOCK"])
        response = lambda_handler(
            self.event(
                {
                    "enterprise_id": "ent-tagro",
                    "name": "Customer",
                    "phone": "9999999999",
                    "idempotency_key": "customer-command-2",
                }
            ),
            None,
        )
        self.assertEqual(403, response["statusCode"])

    def test_sam_route_is_authenticated(self):
        text = open("architecture/aws/nonprod-runtime-template.yaml", encoding="utf-8").read()
        self.assertIn("Path: /customers", text)
        block = text.split("CustomerCreate:", 1)[1].split("OwnerOnCall:", 1)[0]
        self.assertIn("Method: POST", block)
        self.assertNotIn("Authorizer: NONE", block)


if __name__ == "__main__":
    unittest.main()
