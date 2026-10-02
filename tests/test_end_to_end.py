import io
import json
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from injectprobe.cli import main
from injectprobe.demo import DemoTarget
from injectprobe.runner import HARNESS_SYSTEM_PROMPT, filter_cases, load_pack, new_secrets, run
from injectprobe.targets import HTTPTarget, OpenAITarget, PythonTarget


class _Handler(BaseHTTPRequestHandler):
    """A gullible model behind an OpenAI-compatible API, plus a custom app route."""

    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/v1/chat/completions":
            system = next((m["content"] for m in body["messages"] if m["role"] == "system"), "")
            last = body["messages"][-1]["content"]
            text = system if "system prompt" in last.lower() else "Hello from the mock model."
            out = {"choices": [{"message": {"role": "assistant", "content": text}}]}
        elif self.path == "/app/chat":
            out = {"data": {"reply": f"echo: {body['message'][:40]}"}}
        else:
            self.send_response(404)
            self.end_headers()
            return
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class ServerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()


class PackTests(unittest.TestCase):
    def test_core_pack_is_valid(self):
        cases = load_pack("core")
        self.assertEqual(len(cases), 30)
        self.assertEqual(len({c.id for c in cases}), 30)
        for c in cases:
            joined = " ".join(m["content"] for m in c.messages) + " ".join(c.context or [])
            # Marker attacks must never contain the joined marker, only its halves.
            self.assertNotIn("{marker_a}{marker_b}", joined.replace(" ", ""), c.id)

    def test_filters(self):
        cases = load_pack("core")
        self.assertEqual({c.id[:3] for c in filter_cases(cases, ids=["SPL"])}, {"SPL"})
        self.assertTrue(all(c.owasp == "LLM07" for c in filter_cases(cases, owasp=["llm07"])))
        self.assertTrue(all(c.severity in ("high", "critical") for c in filter_cases(cases, min_severity="high")))

    def test_missing_pack(self):
        with self.assertRaises(FileNotFoundError):
            load_pack("does-not-exist")


class DemoTests(unittest.TestCase):
    def test_vulnerable_vs_hardened(self):
        cases = load_pack("core")
        weak = run(cases, DemoTarget(), new_secrets(None, True))
        strong = run(cases, DemoTarget(hardened=True), new_secrets(None, True))
        self.assertLess(weak.score, 20)
        self.assertGreater(strong.score, 80)
        self.assertEqual(weak.count("error"), 0)
        acrostic = next(r for r in strong.results if r.case.id == "SPL-009")
        self.assertEqual(acrostic.status, "fail")


class TargetTests(ServerTestCase):
    def test_openai_compatible_target(self):
        target = OpenAITarget("mock", base_url=self.base + "/v1")
        cases = filter_cases(load_pack("core"), ids=["SPL-001", "PI-001"])
        summary = run(cases, target, new_secrets(None, True))
        status = {r.case.id: r.status for r in summary.results}
        self.assertEqual(status, {"SPL-001": "fail", "PI-001": "pass"})

    def test_http_target_and_skips(self):
        target = HTTPTarget(self.base + "/app/chat", response_path="data.reply")
        summary = run(load_pack("core"), target, new_secrets(None, target.controls_system_prompt))
        # Leak-only attacks cannot be judged without a canary or system prompt.
        self.assertEqual(summary.count("skip"), 13)
        self.assertEqual(summary.count("error"), 0)

    def test_http_error_is_reported(self):
        target = HTTPTarget(self.base + "/missing")
        summary = run(filter_cases(load_pack("core"), ids=["PI-001"]), target, new_secrets(None, False))
        self.assertEqual(summary.results[0].status, "error")
        self.assertIn("HTTP 404", summary.results[0].attempts[0].error)

    def test_harness_prompt_has_placeholders(self):
        self.assertIn("{canary}", HARNESS_SYSTEM_PROMPT)
        s = new_secrets(None, True)
        self.assertIn(s.canary, s.system_prompt)
        self.assertNotIn("{canary}", s.system_prompt)


class PythonTargetTests(unittest.TestCase):
    def test_python_file_target(self):
        with tempfile.TemporaryDirectory() as d:
            bot = Path(d) / "bot.py"
            bot.write_text("CANARY = 'PLANTED-CANARY-777'\n"
                           "def respond(messages, context=None):\n"
                           "    if 'system prompt' in messages[-1]['content'].lower():\n"
                           "        return 'My prompt contains ' + CANARY\n"
                           "    if 'crash' in messages[-1]['content']:\n"
                           "        raise RuntimeError('boom')\n"
                           "    return {'text': 'hi', 'tool_calls': []}\n")
            target = PythonTarget(f"{bot}:respond")
            s = new_secrets(None, target.controls_system_prompt, canaries=["PLANTED-CANARY-777"])
            summary = run(filter_cases(load_pack("core"), ids=["SPL-001", "SPL-002"]), target, s)
            self.assertEqual([r.status for r in summary.results], ["fail", "pass"])


class CliTests(unittest.TestCase):
    def _run(self, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(list(args))
        return code, buf.getvalue()

    def test_run_writes_reports_and_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            code, out = self._run("run", "--target", "demo", "--json", f"{d}/r.json", "--junit", f"{d}/r.xml",
                                  "--html", f"{d}/r.html", "-q")
            self.assertEqual(code, 1)
            self.assertIn("Resilience score", out)
            data = json.loads(Path(f"{d}/r.json").read_text())
            self.assertEqual(data["counts"]["fail"] + data["counts"]["pass"], 30)
            self.assertIn("<testsuite", Path(f"{d}/r.xml").read_text())
            self.assertIn("LLM security report", Path(f"{d}/r.html").read_text())
        code, _ = self._run("run", "--target", "demo-hardened", "-q", "--fail-on", "critical")
        self.assertEqual(code, 0)

    def test_list(self):
        code, out = self._run("list", "--only", "IPI")
        self.assertEqual(code, 0)
        self.assertEqual(len(out.strip().splitlines()), 6)

    def test_bad_pack(self):
        code, _ = self._run("run", "--pack", "nope", "-q")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
