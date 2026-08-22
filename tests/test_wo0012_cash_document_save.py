from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from src.aws_runtime.handler import lambda_handler


class ClosingCashDocumentSaveTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "ECHO_ENV": "nonprod", "AWS_REGION": "ap-south-1", "DB_SECRET_ARN": "arn:test",
            "DB_HOST": "private", "DB_PORT": "5432", "DB_NAME": "echoos",
        }, clear=False)
        self.env.start()

    def tearDown(self):
        self.env.stop()

    @staticmethod
    def event(payload):
        return {
            "rawPath": "/cash-days/save",
            "body": json.dumps(payload),
            "requestContext": {"http": {"method": "POST"}, "authorizer": {"jwt": {"claims": {"sub": "staff-1"}}}},
        }

    @patch("src.aws_runtime.handler.save_cash_document")
    @patch("src.aws_runtime.handler.tenant_context")
    def test_save_route_requires_cash_and_returns_document_contract(self, context_mock, save_mock):
        context_mock.return_value = {
            "principal_id": "principal-1",
            "enterprises": [{"membership_id": "mem-1", "enterprise_id": "ent-tagro", "role_code": "STAFF", "capabilities": ["CASH"]}],
        }
        save_mock.return_value = {"document_id": "doc-1", "shared_persistence": "confirmed"}
        response = lambda_handler(self.event({"enterprise_id": "ent-tagro"}), None)
        body = json.loads(response["body"])
        self.assertEqual(201, response["statusCode"])
        self.assertEqual("tagro.echo.cash-document-saved.v1", body["schema"])
        self.assertEqual("confirmed", body["data"]["shared_persistence"])

    @patch("src.aws_runtime.handler.tenant_context")
    def test_save_route_rejects_membership_without_cash(self, context_mock):
        context_mock.return_value = {
            "principal_id": "principal-1",
            "enterprises": [{"membership_id": "mem-1", "enterprise_id": "ent-tagro", "role_code": "STAFF", "capabilities": ["SELL"]}],
        }
        response = lambda_handler(self.event({"enterprise_id": "ent-tagro"}), None)
        self.assertEqual(403, response["statusCode"])

    def test_migration_and_sam_admit_exact_saved_document(self):
        schema = open("schemas/business/cash_saved_document_v0_4.sql", encoding="utf-8").read()
        self.assertIn("document_json jsonb not null", schema)
        self.assertIn("rendered_image_png bytea", schema)
        self.assertIn("request_hash text not null", schema)
        manifest = json.load(open("schemas/migrations/nonprod_v0_2_manifest.json", encoding="utf-8"))
        ids = [m["id"] for m in manifest["migrations"]]
        self.assertIn("0011-cash-saved-document-v0.4", ids)
        sam = open("architecture/aws/nonprod-runtime-template.yaml", encoding="utf-8").read()
        self.assertIn("Path: /cash-days/save", sam)
        block = sam.split("CashDocumentSave:", 1)[1].split("BillingIssue:", 1)[0]
        self.assertNotIn("Authorizer: NONE", block)


if __name__ == "__main__":
    unittest.main()
