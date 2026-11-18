import importlib.util
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "dns_propagation", ROOT / "src/cert-generator/dns_propagation.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Clock:
    def __init__(self):
        self.now = 0
        self.sleeps = []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class PropagationTests(unittest.TestCase):
    def test_defaults_and_invalid_wait_settings(self):
        self.assertEqual(module.propagation_settings({}), (120, 600))
        for env in [{"DNS_PROPAGATION_SECONDS": "0"}, {"DNS_PROPAGATION_SECONDS": "bad"},
                    {"DNS_PROPAGATION_TIMEOUT_SECONDS": "120"},
                    {"DNS_PROPAGATION_TIMEOUT_SECONDS": "901"}]:
            with self.assertRaises(ValueError):
                module.propagation_settings(env)

    def test_waits_before_lookup_and_waits_for_this_challenges_value(self):
        clock = Clock()
        output = io.StringIO()
        lookup = Mock(side_effect=[set(), {"previous-challenge"}, {"current-challenge"}])
        with patch("sys.stdout", output):
            module.wait_for_txt("_acme-challenge.example.com", "current-challenge",
                                delay=30, timeout=80, lookup=lookup,
                                clock=clock.time, sleep=clock.sleep)
        self.assertEqual(clock.sleeps, [30, 10, 10])
        self.assertEqual(lookup.call_count, 3)
        self.assertIn('"status": "ready"', output.getvalue())
        self.assertNotIn("current-challenge", output.getvalue())

    def test_lookup_errors_and_missing_txt_timeout_with_bounded_wait(self):
        clock = Clock()
        output = io.StringIO()
        lookup = Mock(side_effect=RuntimeError("do-not-log-error-body"))
        with patch("sys.stdout", output), self.assertRaisesRegex(RuntimeError, "DNS propagation timed out"):
            module.wait_for_txt("_acme-challenge.example.com", "current-challenge",
                                delay=30, timeout=55, lookup=lookup,
                                clock=clock.time, sleep=clock.sleep)
        self.assertEqual(clock.now, 55)
        self.assertNotIn("do-not-log-error-body", output.getvalue())
        self.assertIn("lookup_error", output.getvalue())

    def test_https_lookup_parses_txt_chunks_and_does_not_send_cloud_credentials(self):
        response = Mock(status_code=200)
        response.json.return_value = {"Status": 0, "Answer": [
            {"type": 16, "data": '"part1" "part2"'},
            {"type": 16, "data": '"other-value"'},
            {"type": 5, "data": "not-a-txt-value"},
        ]}
        get = Mock(return_value=response)
        with patch.dict(sys.modules, {"requests": SimpleNamespace(get=get)}):
            self.assertEqual(module.public_txt_values("_acme-challenge.example.com", 5),
                             {"part1part2", "other-value"})
        get.assert_called_once_with("https://dns.alidns.com/resolve",
                                    params={"name": "_acme-challenge.example.com", "type": "TXT"},
                                    headers={"Accept": "application/dns-json"},
                                    timeout=5, allow_redirects=False)
        response.close.assert_called_once()

    def test_nxdomain_is_not_ready_and_dnssec_or_http_errors_do_not_pass(self):
        response = Mock(status_code=200)
        response.json.return_value = {"Status": 3}
        with patch.dict(sys.modules, {"requests": SimpleNamespace(get=Mock(return_value=response))}):
            self.assertEqual(module.public_txt_values("example.com", 5), set())
            response.json.return_value = {"Status": 2}
            with self.assertRaises(RuntimeError):
                module.public_txt_values("example.com", 5)
            response.status_code = 302
            with self.assertRaises(RuntimeError):
                module.public_txt_values("example.com", 5)


if __name__ == "__main__":
    unittest.main()
