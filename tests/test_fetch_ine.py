"""Offline behavioral tests; payloads are synthetic, not INE evidence."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import requests

from src.data.fetch_ine import fetch_ine

URL = "https://example.invalid/test-only"


def response(status=200, content=b'{ "records": [{"synthetic": "001"}] }\n', headers=None):
    result = requests.Response()
    result.status_code = status
    result._content = content
    result._content_consumed = True
    result.headers.update(headers or {})
    result.url = URL
    return result


class FetchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name)

    @patch("src.data.fetch_ine.requests.get")
    def test_success_preserves_exact_bytes_and_timeout(self, get):
        original = b'  {"a": [1], "text": "Portugal"}\n'
        get.return_value = response(content=original)
        path = fetch_ine(URL, "sample", self.output)
        self.assertEqual(path, self.output / "sample.json")
        self.assertEqual(path.read_bytes(), original)
        get.assert_called_once_with(URL, timeout=30.0)

    @patch("src.data.fetch_ine.time.sleep")
    @patch("src.data.fetch_ine.requests.get")
    def test_permanent_http_error_is_not_retried_or_saved(self, get, sleep):
        get.return_value = response(status=404)
        with self.assertRaises(requests.HTTPError):
            fetch_ine(URL, "sample", self.output)
        get.assert_called_once()
        sleep.assert_not_called()
        self.assertFalse((self.output / "sample.json").exists())

    @patch("src.data.fetch_ine.time.sleep")
    @patch("src.data.fetch_ine.requests.get")
    def test_each_temporary_status_retries_and_logs(self, get, sleep):
        for status in (429, 500, 502, 503, 504):
            with self.subTest(status=status):
                get.reset_mock()
                sleep.reset_mock()
                get.side_effect = [response(status), response()]
                with self.assertLogs("src.data.fetch_ine", level="WARNING") as logs:
                    path = fetch_ine(URL, f"status_{status}", self.output)
                self.assertTrue(path.exists())
                self.assertEqual(get.call_count, 2)
                sleep.assert_called_once_with(1.0)
                self.assertIn(f"HTTP {status}; retry 1/3", logs.output[0])

    @patch("src.data.fetch_ine.time.sleep")
    @patch("src.data.fetch_ine.requests.get")
    def test_retry_limit_and_exponential_backoff(self, get, sleep):
        get.side_effect = [response(503) for _ in range(4)]
        with self.assertRaises(requests.HTTPError):
            fetch_ine(URL, "sample", self.output, max_retries=3)
        self.assertEqual(get.call_count, 4)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1.0, 2.0, 4.0])
        self.assertFalse((self.output / "sample.json").exists())

    @patch("src.data.fetch_ine.time.sleep")
    @patch("src.data.fetch_ine.requests.get")
    def test_retry_after_is_respected(self, get, sleep):
        get.side_effect = [response(429, headers={"Retry-After": "7"}), response()]
        fetch_ine(URL, "sample", self.output)
        sleep.assert_called_once_with(7.0)

    @patch("src.data.fetch_ine.time.sleep")
    @patch("src.data.fetch_ine.requests.get")
    def test_network_failures_retry(self, get, sleep):
        get.side_effect = [requests.Timeout("test"), requests.ConnectionError("test"), response()]
        fetch_ine(URL, "sample", self.output)
        self.assertEqual(get.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1.0, 2.0])

    @patch("src.data.fetch_ine.time.sleep")
    @patch("src.data.fetch_ine.requests.get")
    def test_zero_retries(self, get, sleep):
        get.return_value = response(500)
        with self.assertRaises(requests.HTTPError):
            fetch_ine(URL, "sample", self.output, max_retries=0)
        get.assert_called_once()
        sleep.assert_not_called()

    @patch("src.data.fetch_ine.requests.get")
    def test_invalid_json_not_saved_or_retried(self, get):
        get.return_value = response(content=b"<html>not JSON</html>")
        with self.assertRaises(ValueError):
            fetch_ine(URL, "sample", self.output)
        get.assert_called_once()
        self.assertFalse((self.output / "sample.json").exists())

    @patch("src.data.fetch_ine.requests.get")
    def test_existing_raw_is_not_overwritten(self, get):
        path = self.output / "sample.json"
        path.write_bytes(b"original")
        with self.assertRaises(FileExistsError):
            fetch_ine(URL, "sample", self.output)
        self.assertEqual(path.read_bytes(), b"original")
        get.assert_not_called()

    @patch("src.data.fetch_ine.requests.get")
    def test_unsafe_filename_is_rejected(self, get):
        with self.assertRaises(ValueError):
            fetch_ine(URL, "../escape", self.output)
        get.assert_not_called()

    @patch("src.data.fetch_ine.requests.get")
    def test_invalid_configuration_is_rejected(self, get):
        for options in ({"timeout": 0}, {"timeout": float("nan")}, {"max_retries": -1}, {"backoff_factor": -1}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                fetch_ine(URL, "sample", self.output, **options)
        get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
