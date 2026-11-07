import ast
import importlib
import os
import unittest
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch


class AllowedHostsTests(unittest.TestCase):
    def settings(self, allowed_hosts=None):
        environment = {"LIMIT": "7", "SESSION_TIMEOUT": "700"}
        if allowed_hosts is not None:
            environment["ALLOWED_HOSTS"] = allowed_hosts
        with patch.dict(os.environ, environment, clear=True):
            module = importlib.import_module("src.a2a_server.config.settings")
            return module.Settings()

    def test_unset_allows_all_hosts(self):
        self.assertEqual(self.settings().ALLOWED_HOSTS, ["*"])

    def test_comma_separated_hosts_and_port_wildcards(self):
        settings = self.settings(" localhost:* , 127.0.0.1:*, *.example.com ")
        self.assertEqual(settings.ALLOWED_HOSTS, ["localhost", "127.0.0.1", "*.example.com"])

    def test_empty_entries_are_rejected(self):
        for value in ("", "localhost,,example.com", "localhost, "):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.settings(value)

    def test_trusted_host_middleware_receives_configured_hosts(self):
        source = Path("src/a2a_server/transport/http/app.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        call = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_middleware"
            and node.args
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "TrustedHostMiddleware"
        )
        app = Mock()
        middleware = object()
        settings = self.settings("localhost:*,example.com")
        expression = ast.Expression(body=call)
        eval(compile(expression, "app.py", "eval"), {
            "app": app,
            "TrustedHostMiddleware": middleware,
            "settings": settings,
        })
        app.add_middleware.assert_called_once_with(
            middleware, allowed_hosts=["localhost", "example.com"]
        )


if __name__ == "__main__":
    unittest.main()
