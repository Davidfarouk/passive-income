---
title: "The OWASP LLM Top 10 (2025): a developer's testing checklist"
description: "A practical, test-oriented walk through the OWASP Top 10 for LLM Applications — what each risk means in code, and how to actually test for it."
tags: [llm, security, owasp, ai, testing]
canonical_cta: "https://github.com/Davidfarouk/passive-income"
---

# The OWASP LLM Top 10 (2025): a developer's testing checklist

The [OWASP Top 10 for LLM Applications](https://genai.owasp.org/llm-top-10/) is the closest thing the field has to a shared security baseline. But the list is written as risks, not tests. Here's the developer's version: what each one means in your code, and how to check whether you're exposed.

### LLM01 — Prompt Injection
**Risk:** user input or retrieved content overrides your instructions.
**Test:** fire override attacks ("ignore previous instructions"), role-spoofing, delimiter escapes, and indirect injections planted in retrieved documents. Confirm the model didn't obey.

### LLM02 — Sensitive Information Disclosure
**Risk:** the model reveals secrets, PII, or other users' data.
**Test:** ask for credentials, other users' records, and config under audit pretexts. Plant a canary and verify it never comes back.

### LLM05 — Improper Output Handling
**Risk:** model output is rendered or executed without sanitization (XSS, SQLi, SSRF).
**Test:** request `<script>` tags, `javascript:` links, SQL payloads, and markdown images to foreign hosts; verify your renderer/ downstream code neutralizes them.

### LLM06 — Excessive Agency
**Risk:** agents call tools they shouldn't, triggered by users or documents.
**Test:** ask for unauthorized refunds, deletions, shell commands, and SSRF fetches; confirm privileged tools require real authorization, not just the model's say-so.

### LLM07 — System Prompt Leakage
**Risk:** your instructions and any embedded secrets leak.
**Test:** repeat-above, translation, base64, acrostic, and completion attacks — with encoding-aware detection so sneaky leaks count.

### LLM10 — Unbounded Consumption
**Risk:** attackers drive cost with huge or recursive generations.
**Test:** request unbounded output; confirm `max_tokens`, rate limits and timeouts hold.

*(LLM03 Supply Chain, LLM04 Data/Model Poisoning, LLM08 Vector Weaknesses and LLM09 Misinformation are largely pipeline- and process-level — covered by dependency scanning, data governance and evals rather than runtime attack testing.)*

## Turning the checklist into a command

Reading a checklist is one thing; running it is another. [`injectprobe`](https://github.com/Davidfarouk/passive-income) maps every attack to one of these categories and reports your pass/fail rate per OWASP item:

```bash
pip install "git+https://github.com/Davidfarouk/passive-income"
injectprobe run --target openai --model gpt-4o-mini --html owasp-report.html
```

The HTML report gives you a per-category breakdown — exactly the evidence you need for a security review or a customer questionnaire.

## Make it continuous

Security regresses silently when prompts, models, or retrieval change. Gate CI:

```bash
injectprobe run --target http --url "$STAGING_URL" --canary "$CANARY" --repeat 3 --fail-on high --junit results.xml
```

The free core pack covers LLM01, LLM02, LLM05 and LLM07. For full coverage including agent/tool-abuse (LLM06), 15+ RAG-poisoning formats and unbounded-consumption probes, plus a hardening playbook and CI templates, see [injectprobe Pro](https://davidfarouk.gumroad.com/l/injectprobe-pro) ($9).

Run `injectprobe demo` and get your first OWASP scorecard in under a minute.
