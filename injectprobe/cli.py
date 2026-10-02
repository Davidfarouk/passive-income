from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional

from . import __version__
from .demo import DemoTarget
from .models import SEVERITY_ORDER
from .report import console_summary, progress_line, to_html, to_json, to_junit
from .runner import filter_cases, load_pack, new_secrets, run
from .targets import AnthropicTarget, HTTPTarget, OpenAITarget, PythonTarget, Target, TargetError, env_key

EPILOG = """examples:
  injectprobe demo
  injectprobe run --target openai --model gpt-4o-mini --html report.html
  injectprobe run --target openai --base-url http://localhost:11434/v1 --model llama3.1
  injectprobe run --target anthropic --model claude-haiku-4-5 --system-prompt-file prompt.txt
  injectprobe run --target http --url https://staging.example.com/chat \\
      --body '{"message": "{prompt}"}' --response-path reply --canary MY-PLANTED-CANARY
  injectprobe run --target python:myapp/bot.py:respond --fail-on high --junit results.xml
"""


def _headers(values: List[str]) -> Dict[str, str]:
    out = {}
    for v in values:
        if ":" not in v:
            raise SystemExit(f"--header must look like 'Name: value', got {v!r}")
        k, _, val = v.partition(":")
        out[k.strip()] = val.strip()
    return out


def build_target(a: argparse.Namespace) -> Target:
    t = a.target
    headers = _headers(a.header)
    if t in ("demo", "demo-hardened"):
        return DemoTarget(hardened=t == "demo-hardened")
    if t == "openai":
        if not a.model:
            raise SystemExit("--model is required for --target openai")
        key = env_key(a.api_key_env, "OPENAI_API_KEY")
        if not key and "api.openai.com" in a.base_url:
            raise SystemExit("set OPENAI_API_KEY (or --api-key-env NAME) to test api.openai.com")
        return OpenAITarget(a.model, a.base_url, key, headers, a.max_tokens, a.temperature, a.timeout)
    if t == "anthropic":
        if not a.model:
            raise SystemExit("--model is required for --target anthropic")
        key = env_key(a.api_key_env, "ANTHROPIC_API_KEY")
        if not key:
            raise SystemExit("set ANTHROPIC_API_KEY (or --api-key-env NAME)")
        base = a.base_url if a.base_url != "https://api.openai.com/v1" else "https://api.anthropic.com/v1"
        return AnthropicTarget(a.model, key, base, headers, a.max_tokens, a.temperature, a.timeout)
    if t == "http":
        if not a.url:
            raise SystemExit("--url is required for --target http")
        return HTTPTarget(a.url, a.body, a.response_path, headers, a.timeout)
    if t.startswith("python:"):
        return PythonTarget(t[len("python:"):])
    raise SystemExit(f"unknown target {t!r} (use openai, anthropic, http, python:module:func, demo, demo-hardened)")


def _add_run_args(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("target")
    g.add_argument("--target", "-t", default="demo",
                   help="openai | anthropic | http | python:module:func | demo | demo-hardened (default: demo)")
    g.add_argument("--model", "-m", help="model name for openai/anthropic targets")
    g.add_argument("--base-url", default="https://api.openai.com/v1",
                   help="API base URL (OpenAI-compatible servers: Ollama, vLLM, Groq, OpenRouter, Azure...)")
    g.add_argument("--api-key-env", help="env var holding the API key (default OPENAI_API_KEY / ANTHROPIC_API_KEY)")
    g.add_argument("--url", help="endpoint for --target http")
    g.add_argument("--body", default='{"message": "{prompt}"}',
                   help='JSON body template for --target http; "{prompt}" and "{messages}" are substituted')
    g.add_argument("--response-path", help="dot path to the reply text in the JSON response, e.g. data.reply")
    g.add_argument("--header", "-H", action="append", default=[], help="extra HTTP header 'Name: value' (repeatable)")
    g.add_argument("--max-tokens", type=int, default=512)
    g.add_argument("--temperature", type=float, default=None)
    g.add_argument("--timeout", type=float, default=60)

    g = p.add_argument_group("detection")
    g.add_argument("--system-prompt-file", type=Path,
                   help="your production system prompt. With openai/anthropic it replaces the built-in harness "
                        "prompt ({canary} and {secret} placeholders are filled in); with http/python it is used to "
                        "detect verbatim leaks")
    g.add_argument("--canary", action="append", default=[],
                   help="a unique string you planted in your app's system prompt; any leak of it fails (repeatable)")
    g.add_argument("--secret-regex", action="append", default=[], help="regex for secrets that must never appear")
    g.add_argument("--allow-domain", action="append", default=[],
                   help="domain your UI may legitimately link/render images from (default: acme.example)")

    g = p.add_argument_group("attacks")
    g.add_argument("--pack", "-p", action="append", default=[],
                   help="attack pack name or path (repeatable, default: core). Packs in ~/.injectprobe/packs/ "
                        "can be referenced by name")
    g.add_argument("--only", action="append", default=[], help="case id or id prefix, e.g. SPL or PI-003")
    g.add_argument("--owasp", action="append", default=[], help="only this OWASP category, e.g. LLM07")
    g.add_argument("--min-severity", choices=list(SEVERITY_ORDER), help="skip attacks below this severity")
    g.add_argument("--repeat", "-r", type=int, default=1,
                   help="attempts per attack; a case fails if any attempt succeeds (LLMs are stochastic)")
    g.add_argument("--concurrency", "-c", type=int, default=4)

    g = p.add_argument_group("output")
    g.add_argument("--html", type=Path, help="write an HTML report")
    g.add_argument("--json", type=Path, help="write a JSON report")
    g.add_argument("--junit", type=Path, help="write JUnit XML (for CI test reporting)")
    g.add_argument("--fail-on", choices=list(SEVERITY_ORDER) + ["never"], default="medium",
                   help="exit 1 if any attack of at least this severity succeeds (default: medium)")
    g.add_argument("--quiet", "-q", action="store_true", help="only print the summary")


def cmd_run(a: argparse.Namespace) -> int:
    try:
        target = build_target(a)
    except TargetError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    cases = []
    for pack in a.pack or ["core"]:
        try:
            cases += load_pack(pack)
        except (FileNotFoundError, ValueError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
    cases = filter_cases(cases, a.only, a.owasp, a.min_severity)
    if not cases:
        print("error: no attacks selected", file=sys.stderr)
        return 2
    system_prompt: Optional[str] = None
    if a.system_prompt_file:
        system_prompt = a.system_prompt_file.read_text(encoding="utf-8")
    secrets = new_secrets(system_prompt, target.controls_system_prompt, a.canary, a.secret_regex,
                          a.allow_domain or ["acme.example"])

    if not a.quiet:
        print(f"\n  injectprobe {__version__} · target {target.name} · {len(cases)} attacks × {max(1, a.repeat)}\n")
    summary = run(cases, target, secrets, a.repeat, a.concurrency, None if a.quiet else progress_line)
    console_summary(summary)
    for path, render in ((a.html, to_html), (a.json, to_json), (a.junit, to_junit)):
        if path:
            path.write_text(render(summary), encoding="utf-8")
            print(f"  wrote {path}")
    if a.fail_on == "never":
        return 0
    floor = SEVERITY_ORDER[a.fail_on]
    breached = [r for r in summary.results if r.status == "fail" and SEVERITY_ORDER[r.case.severity] >= floor]
    if summary.count("error") == len(summary.results):
        print("  every request failed: check the target configuration", file=sys.stderr)
        return 2
    return 1 if breached else 0


def cmd_list(a: argparse.Namespace) -> int:
    cases = []
    for pack in a.pack or ["core"]:
        cases += load_pack(pack)
    for c in filter_cases(cases, a.only, a.owasp, a.min_severity):
        print(f"{c.id:<9} {c.owasp}  {c.severity:<8} {c.technique:<24} {c.title}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="injectprobe", description="Prompt-injection and system-prompt-leak testing for LLM apps.",
        epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=f"injectprobe {__version__}")
    sub = parser.add_subparsers(dest="cmd")

    p_run = sub.add_parser("run", help="run attacks against a target", epilog=EPILOG,
                           formatter_class=argparse.RawDescriptionHelpFormatter)
    _add_run_args(p_run)
    p_demo = sub.add_parser("demo", help="run the core pack against a built-in vulnerable bot (no API key needed)")
    p_demo.add_argument("--hardened", action="store_true", help="use the hardened demo bot instead")
    p_demo.add_argument("--html", type=Path, default=Path("injectprobe-demo.html"))
    p_list = sub.add_parser("list", help="list the attacks in a pack")
    p_list.add_argument("--pack", "-p", action="append", default=[])
    p_list.add_argument("--only", action="append", default=[])
    p_list.add_argument("--owasp", action="append", default=[])
    p_list.add_argument("--min-severity", choices=list(SEVERITY_ORDER))

    a = parser.parse_args(argv)
    if a.cmd == "run":
        return cmd_run(a)
    if a.cmd == "demo":
        demo_args = parser.parse_args(["run", "--target", "demo-hardened" if a.hardened else "demo",
                                       "--html", str(a.html), "--fail-on", "never"])
        return cmd_run(demo_args)
    if a.cmd == "list":
        return cmd_list(a)
    parser.print_help()
    return 0
