"""Regression tests for Kemo HTTP transport behavior."""

from __future__ import annotations

import sys
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from provider.kemo_adapter import _is_loopback_url, _urlopen


class LoopbackProxyBypassTests(unittest.TestCase):
    def test_loopback_detection_covers_common_local_addresses(self):
        self.assertTrue(_is_loopback_url("http://127.0.0.1:8741/v1"))
        self.assertTrue(_is_loopback_url("http://localhost:8741/v1"))
        self.assertTrue(_is_loopback_url("http://[::1]:8741/v1"))
        self.assertFalse(_is_loopback_url("https://api.example.com/v1"))

    @patch("provider.kemo_adapter.urllib.request.urlopen")
    @patch("provider.kemo_adapter.urllib.request.build_opener")
    def test_loopback_request_uses_proxy_free_opener(self, build_opener, urlopen):
        response = object()
        opener = Mock()
        opener.open.return_value = response
        build_opener.return_value = opener
        request = urllib.request.Request("http://127.0.0.1:8741/v1/models")

        self.assertIs(_urlopen(request, timeout=12), response)

        proxy_handler = build_opener.call_args.args[0]
        self.assertEqual(proxy_handler.proxies, {})
        opener.open.assert_called_once_with(request, timeout=12)
        urlopen.assert_not_called()

    @patch("provider.kemo_adapter.urllib.request.urlopen")
    @patch("provider.kemo_adapter.urllib.request.build_opener")
    def test_external_request_keeps_environment_proxy_behavior(self, build_opener, urlopen):
        response = object()
        urlopen.return_value = response
        request = urllib.request.Request("https://api.example.com/v1/models")

        self.assertIs(_urlopen(request, timeout=34), response)

        urlopen.assert_called_once_with(request, timeout=34)
        build_opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
