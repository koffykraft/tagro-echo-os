from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from src.aws_runtime.handler import lambda_handler
from src.aws_runtime.reference_runtime import ReferenceRuntimeError, _limit


class ReferenceRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "ECHO_ENV":"nonprod","AWS_REGION":"ap-south-1","DB_SECRET_ARN":"arn:test","DB_HOST":"private","DB_PORT":"5432","DB_NAME":"echoos"
        }, clear=False)
        self.env.start()

    def tearDown(self):
        self.env.stop()

    @staticmethod
    def event(query=None):
        return {
            "rawPath":"/reference-data",
            "queryStringParameters":query or {},
            "requestContext":{"http":{"method":"GET"},"authorizer":{"jwt":{"claims":{"sub":"staff-1"}}}},
        }

    @patch("src.aws_runtime.handler.reference_search")
    @patch("src.aws_runtime.handler.tenant_context")
    def test_reference_search_uses_server_membership_scope(self, context_mock, search_mock):
        context_mock.return_value={"principal_id":"p1","enterprises":[{"enterprise_id":"ent-tagro","role_code":"STAFF","capabilities":["SELL"]}]}
        search_mock.return_value={"schema":"tagro.echo.reference-data.v1","kind":"products","items":[],"read_only":True}
        response=lambda_handler(self.event({"kind":"products","q":"ms 182","limit":"20"}),None)
        self.assertEqual(200,response["statusCode"])
        search_mock.assert_called_once_with(unittest.mock.ANY,enterprise_id="ent-tagro",kind="products",query="ms 182",limit="20")

    @patch("src.aws_runtime.handler.tenant_context")
    def test_multiple_enterprises_require_selection(self, context_mock):
        context_mock.return_value={"principal_id":"p1","enterprises":[{"enterprise_id":"a"},{"enterprise_id":"b"}]}
        response=lambda_handler(self.event({"kind":"products"}),None)
        self.assertEqual(409,response["statusCode"])

    @patch("src.aws_runtime.handler.reference_search")
    @patch("src.aws_runtime.handler.tenant_context")
    def test_invalid_reference_query_returns_400(self, context_mock, search_mock):
        context_mock.return_value={"principal_id":"p1","enterprises":[{"enterprise_id":"ent-tagro"}]}
        search_mock.side_effect=ReferenceRuntimeError("unsupported reference kind")
        response=lambda_handler(self.event({"kind":"anything"}),None)
        self.assertEqual(400,response["statusCode"])
        self.assertEqual("invalid_reference_query",json.loads(response["body"])["error"])

    def test_limit_is_bounded(self):
        self.assertEqual(40,_limit(None))
        self.assertEqual(100,_limit("100"))
        with self.assertRaises(ReferenceRuntimeError): _limit(101)
        with self.assertRaises(ReferenceRuntimeError): _limit(0)

    def test_route_is_jwt_protected_in_sam(self):
        text=open("architecture/aws/nonprod-runtime-template.yaml",encoding="utf-8").read()
        self.assertIn("Path: /reference-data",text)
        block=text.split("ReferenceData:",1)[1].split("OwnerOnCall:",1)[0]
        self.assertNotIn("Authorizer: NONE",block)


if __name__ == "__main__": unittest.main()
