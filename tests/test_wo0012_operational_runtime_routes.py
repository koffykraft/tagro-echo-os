from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from src.aws_runtime.handler import lambda_handler


class OperationalRuntimeRouteTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "ECHO_ENV":"nonprod","AWS_REGION":"ap-south-1","DB_SECRET_ARN":"arn:test","DB_HOST":"private","DB_PORT":"5432","DB_NAME":"echoos"
        }, clear=False)
        self.env.start()

    def tearDown(self):
        self.env.stop()

    @staticmethod
    def event(path, payload):
        return {
            "rawPath": path,
            "body": json.dumps(payload),
            "requestContext": {"http":{"method":"POST"},"authorizer":{"jwt":{"claims":{"sub":"staff-1"}}}},
        }

    @staticmethod
    def context(capability):
        return {
            "principal_id":"principal-1",
            "enterprises":[{"membership_id":"mem-1","enterprise_id":"ent-tagro","role_code":"STAFF","capabilities":[capability]}],
        }

    @patch("src.aws_runtime.handler.create_service_intake")
    @patch("src.aws_runtime.handler.tenant_context")
    def test_service_intake_uses_service_capability(self, context_mock, operation_mock):
        context_mock.return_value=self.context("SERVICE")
        operation_mock.return_value={"job_id":"job-1","status":"received"}
        response=lambda_handler(self.event("/service/intake", {"enterprise_id":"ent-tagro"}),None)
        self.assertEqual(201,response["statusCode"])
        self.assertEqual("tagro.echo.service-intake.v1",json.loads(response["body"])["schema"])

    @patch("src.aws_runtime.handler.create_purchase_order")
    @patch("src.aws_runtime.handler.tenant_context")
    def test_purchase_order_uses_purchase_capability(self, context_mock, operation_mock):
        context_mock.return_value=self.context("PURCHASE")
        operation_mock.return_value={"po_id":"po-1","status":"draft"}
        response=lambda_handler(self.event("/purchase-orders", {"enterprise_id":"ent-tagro"}),None)
        self.assertEqual(201,response["statusCode"])
        self.assertEqual("tagro.echo.purchase-order.v1",json.loads(response["body"])["schema"])

    @patch("src.aws_runtime.handler.record_stock_count")
    @patch("src.aws_runtime.handler.tenant_context")
    def test_stock_count_uses_stock_capability_and_does_not_claim_mutation(self, context_mock, operation_mock):
        context_mock.return_value=self.context("STOCK")
        operation_mock.return_value={"count_id":"count-1","stock_mutated":False,"variance":"2"}
        response=lambda_handler(self.event("/stock-count/record", {"enterprise_id":"ent-tagro"}),None)
        body=json.loads(response["body"])
        self.assertEqual(201,response["statusCode"])
        self.assertFalse(body["data"]["stock_mutated"])

    @patch("src.aws_runtime.handler.tenant_context")
    def test_wrong_capability_is_rejected(self, context_mock):
        context_mock.return_value=self.context("SELL")
        response=lambda_handler(self.event("/stock-count/record", {"enterprise_id":"ent-tagro"}),None)
        self.assertEqual(403,response["statusCode"])

    def test_all_operational_post_routes_are_jwt_protected_in_sam(self):
        text=open("architecture/aws/nonprod-runtime-template.yaml",encoding="utf-8").read()
        for path in ("/service/intake","/purchase-orders","/stock-count/record"):
            self.assertIn(f"Path: {path}",text)
        for block_name in ("ServiceIntake:","PurchaseOrderCreate:","StockCountRecord:"):
            block=text.split(block_name,1)[1].split("Type: HttpApi",1)[1].split("Method: POST",1)[0]
            self.assertNotIn("Authorizer: NONE",block)


if __name__ == "__main__":
    unittest.main()
