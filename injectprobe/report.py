from __future__ import annotations

import html
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Dict, Optional, TextIO

from . import __version__
from .models import CaseResult, RunSummary

REMEDIATION: Dict[str, str] = {
    "LLM01": "Treat retrieved documents, tool output and user text as data: wrap them in clearly delimited blocks, "
             "tell the model they are untrusted, and never let them change the task. Keep privileged actions "
             "outside the model's control and re-validate them server-side.",
    "LLM02": "Never put credentials, keys or other users' data in the prompt. Anything in the context window can be "
             "extracted. Fetch sensitive data via tools that enforce the caller's own permissions.",
    "LLM05": "Encode model output for the context it lands in (HTML-escape, parameterize SQL, sanitize markdown). "
             "Disable remote images and auto-linking in chat UIs, or proxy them through an allowlist.",
    "LLM06": "Give the agent the fewest tools possible, scope each tool to the current user, and require human "
             "confirmation for irreversible or costly actions.",
    "LLM07": "Assume the system prompt will leak: keep secrets and authorization logic out of it. Add an output "
             "filter that blocks responses containing planted canary strings, including encoded forms.",
    "LLM10": "Cap max tokens, rate-limit per user, and set timeouts and budget alerts on every model call.",
}

_COLOR = {"pass": "32", "fail": "31", "error": "33", "skip": "90"}


def _c(text: str, code: str, enabled: bool) -> str:
    return f"\033[{code}m{text}\033[0m" if enabled else text


def _use_color(stream: TextIO) -> bool:
    return hasattr(stream, "isatty") and stream.isatty() and os.environ.get("NO_COLOR") is None


def progress_line(r: CaseResult, stream: Optional[TextIO] = None) -> None:
    stream = stream or sys.stdout
    color = _use_color(stream)
    label = {"pass": "PASS", "fail": "FAIL", "error": "ERR ", "skip": "SKIP"}[r.status]
    detail = ""
    if r.status == "fail":
        f = r.first_failure.findings[0]  # type: ignore[union-attr]
        rate = f" [{r.failed_attempts}/{len(r.attempts)}]" if len(r.attempts) > 1 else ""
        detail = f"{f.detail}{rate}"
    elif r.status == "error":
        detail = (r.attempts[-1].error or "")[:90]
    elif r.status == "skip":
        detail = r.skipped_reason or ""
    print(f"  {_c(label, _COLOR[r.status], color)}  {r.case.id:<8} {r.case.severity:<8} {r.case.title[:46]:<46}  "
          f"{_c(detail, '90', color)}", file=stream)


def console_summary(s: RunSummary, stream: Optional[TextIO] = None) -> None:
    stream = stream or sys.stdout
    color = _use_color(stream)
    grade_color = {"A": "32", "B": "32", "C": "33", "D": "33", "F": "31"}[s.grade]
    print(file=stream)
    print(f"  Resilience score: {_c(f'{s.score}/100 ({s.grade})', grade_color + ';1', color)}   "
          f"{s.count('fail')} failed · {s.count('pass')} passed · {s.count('error')} errors · "
          f"{s.count('skip')} skipped · {s.duration_s:.1f}s", file=stream)
    print(file=stream)
    for row in s.by_owasp():
        tested = row["pass"] + row["fail"]
        bar = ("█" * row["fail"] + "░" * row["pass"])[:30]
        print(f"  {row['owasp']} {row['title']:<34} {_c(bar, '31', color)}  {row['fail']}/{tested} vulnerable",
              file=stream)
    print(file=stream)


def _result_dict(r: CaseResult) -> dict:
    return {
        "id": r.case.id, "title": r.case.title, "owasp": r.case.owasp, "category": r.case.category,
        "severity": r.case.severity, "technique": r.case.technique, "status": r.status,
        "failed_attempts": r.failed_attempts, "attempts": len(r.attempts),
        "skipped_reason": r.skipped_reason,
        "messages": r.rendered_messages, "context": r.rendered_context,
        "results": [
            {"response": a.response.text if a.response else None,
             "tool_calls": a.response.tool_calls if a.response else [],
             "latency_ms": round(a.response.latency_ms) if a.response else None,
             "error": a.error,
             "findings": [{"detector": f.detector, "detail": f.detail, "evidence": f.evidence} for f in a.findings]}
            for a in r.attempts
        ],
    }


def to_json(s: RunSummary) -> str:
    return json.dumps({
        "tool": "injectprobe", "version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target": s.target_name, "repeat": s.repeat, "duration_s": round(s.duration_s, 2),
        "score": s.score, "grade": s.grade,
        "counts": {k: s.count(k) for k in ("pass", "fail", "error", "skip")},
        "by_owasp": s.by_owasp(),
        "results": [_result_dict(r) for r in s.results],
    }, indent=2, ensure_ascii=False)


def to_junit(s: RunSummary) -> str:
    suite = ET.Element("testsuite", name="injectprobe", tests=str(len(s.results)),
                       failures=str(s.count("fail")), errors=str(s.count("error")),
                       skipped=str(s.count("skip")), time=f"{s.duration_s:.2f}")
    for r in s.results:
        tc = ET.SubElement(suite, "testcase", classname=f"injectprobe.{r.case.owasp}",
                           name=f"{r.case.id} {r.case.title}")
        if r.status == "fail":
            f = r.first_failure.findings[0]  # type: ignore[union-attr]
            el = ET.SubElement(tc, "failure", message=f"[{r.case.severity}] {f.detail}", type=f.detector)
            el.text = f"Evidence: {f.evidence}\n\nResponse:\n{r.first_failure.response.text if r.first_failure.response else ''}"  # type: ignore[union-attr]
        elif r.status == "error":
            ET.SubElement(tc, "error", message=(r.attempts[-1].error or "")[:500])
        elif r.status == "skip":
            ET.SubElement(tc, "skipped", message=r.skipped_reason or "")
    return ET.tostring(suite, encoding="unicode")


_CSS = """
:root{--bg:#f7f7f8;--card:#fff;--fg:#1d1d21;--muted:#6b6b76;--line:#e4e4e9;--fail:#d92d20;--pass:#12a150;--warn:#d98a00;--code:#f1f1f4}
@media (prefers-color-scheme:dark){:root{--bg:#121214;--card:#1b1b1f;--fg:#ececf1;--muted:#9a9aa6;--line:#2c2c33;--fail:#ff6b5e;--pass:#3ddc84;--warn:#ffb020;--code:#24242a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1040px;margin:0 auto;padding:32px 16px 64px}h1{font-size:24px;margin:0 0 4px}h2{font-size:18px;margin:32px 0 12px}
.muted{color:var(--muted)}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-top:20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}.big{font-size:30px;font-weight:700}
.grade-A,.grade-B{color:var(--pass)}.grade-C,.grade-D{color:var(--warn)}.grade-F{color:var(--fail)}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}
th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}th{font-size:13px;color:var(--muted);font-weight:600}
.bar{height:8px;border-radius:4px;background:var(--line);overflow:hidden;min-width:80px}.bar>span{display:block;height:100%;background:var(--fail)}
.pill{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;font-weight:600;border:1px solid currentColor}
.s-fail{color:var(--fail)}.s-pass{color:var(--pass)}.s-error{color:var(--warn)}.s-skip{color:var(--muted)}
details{background:var(--card);border:1px solid var(--line);border-radius:12px;margin:8px 0;padding:0 16px}
summary{cursor:pointer;padding:12px 0;display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}summary::-webkit-details-marker{display:none}
pre{background:var(--code);padding:12px;border-radius:8px;white-space:pre-wrap;word-break:break-word;font-size:13px;margin:6px 0 12px}
.label{font-size:12px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.fix{border-left:3px solid var(--pass);padding:4px 12px;margin:8px 0 16px}footer{margin-top:40px;font-size:13px}
a{color:inherit}
"""


def to_html(s: RunSummary, title: Optional[str] = None) -> str:
    e = html.escape
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rows = []
    for row in s.by_owasp():
        tested = row["pass"] + row["fail"]
        pct = round(100 * row["fail"] / tested) if tested else 0
        rows.append(f"<tr><td><b>{e(row['owasp'])}</b> {e(row['title'])}</td><td>{row['fail']} / {tested}</td>"
                    f"<td><div class='bar'><span style='width:{pct}%'></span></div></td></tr>")
    order = {"fail": 0, "error": 1, "pass": 2, "skip": 3}
    sev = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    items = []
    for r in sorted(s.results, key=lambda r: (order[r.status], sev.get(r.case.severity, 9), r.case.id)):
        body = [f"<p class='muted'>{e(r.case.description)}</p>"]
        for m in r.rendered_messages:
            body.append(f"<div class='label'>{e(m['role'])}</div><pre>{e(m['content'])}</pre>")
        for i, doc in enumerate(r.rendered_context or [], 1):
            body.append(f"<div class='label'>retrieved document {i}</div><pre>{e(doc)}</pre>")
        attempt = r.first_failure or (r.attempts[-1] if r.attempts else None)
        if attempt and attempt.response:
            body.append(f"<div class='label'>response</div><pre>{e(attempt.response.text) or '(empty)'}</pre>")
            if attempt.response.tool_calls:
                body.append(f"<div class='label'>tool calls</div><pre>{e(json.dumps(attempt.response.tool_calls, indent=2))}</pre>")
        if attempt and attempt.error:
            body.append(f"<div class='label'>error</div><pre>{e(attempt.error)}</pre>")
        if r.status == "fail":
            for f in r.first_failure.findings:  # type: ignore[union-attr]
                body.append(f"<div class='label'>finding · {e(f.detector)}</div><pre>{e(f.detail)}\n{e(f.evidence)}</pre>")
            if r.case.owasp in REMEDIATION:
                body.append(f"<div class='label'>how to fix</div><div class='fix'>{e(REMEDIATION[r.case.owasp])}</div>")
        if r.skipped_reason:
            body.append(f"<p class='muted'>Skipped: {e(r.skipped_reason)}</p>")
        rate = f" · {r.failed_attempts}/{len(r.attempts)} attempts" if len(r.attempts) > 1 and r.status == "fail" else ""
        items.append(
            f"<details{' open' if r.status == 'fail' and r.case.severity in ('critical', 'high') and len(items) < 3 else ''}>"
            f"<summary><span class='pill s-{r.status}'>{r.status.upper()}</span><b>{e(r.case.id)}</b>"
            f"<span>{e(r.case.title)}</span><span class='muted'>{e(r.case.owasp)} · {e(r.case.severity)}"
            f"{rate}</span></summary>{''.join(body)}</details>")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title or 'injectprobe report')}</title><style>{_CSS}</style></head><body><main>
<h1>{e(title or 'LLM security report')}</h1>
<div class="muted">Target <b>{e(s.target_name)}</b> · {len(s.results)} attacks × {s.repeat} attempt(s) · {now} · injectprobe {__version__}</div>
<div class="cards">
<div class="card"><div class="label">Resilience score</div><div class="big grade-{s.grade}">{s.score}<span class="muted" style="font-size:16px">/100 · {s.grade}</span></div></div>
<div class="card"><div class="label">Vulnerable</div><div class="big s-fail">{s.count('fail')}</div></div>
<div class="card"><div class="label">Resisted</div><div class="big s-pass">{s.count('pass')}</div></div>
<div class="card"><div class="label">Errors / skipped</div><div class="big muted">{s.count('error')} / {s.count('skip')}</div></div>
</div>
<h2>By OWASP Top 10 for LLM Applications (2025)</h2>
<table><tr><th>Category</th><th>Vulnerable</th><th style="width:40%"></th></tr>{''.join(rows)}</table>
<h2>Attacks</h2>{''.join(items)}
<footer class="muted">Generated by <a href="https://github.com/Davidfarouk/passive-income">injectprobe</a>. Score is severity-weighted (critical 10, high 5, medium 2, low 1). Canary values are random per run and safe to share.</footer>
</main></body></html>"""
