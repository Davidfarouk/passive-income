---
title: "How to test your LLM app for prompt injection in 60 seconds"
description: "A practical, copy-paste guide to finding prompt-injection and system-prompt-leak bugs in any chatbot, RAG app or agent — with a free, zero-dependency CLI."
tags: [llm, security, prompt-injection, owasp, ai]
canonical_cta: "https://github.com/Davidfarouk/passive-income"
---

# How to test your LLM app for prompt injection in 60 seconds

If you've shipped anything built on an LLM — a support chatbot, a RAG assistant, an agent with tools — there's a question you probably can't answer yet: **is it injectable?** Can a user (or a document it reads) override your instructions, extract your system prompt, or trick it into leaking data?

Most teams find out the hard way, in a screenshot on social media. Here's how to find out in a minute instead.

## The 60-second version

[`injectprobe`](https://github.com/Davidfarouk/passive-income) is a zero-dependency Python CLI that fires a battery of prompt-injection and system-prompt-leak attacks at an LLM target and scores the result against the [OWASP Top 10 for LLM Applications (2025)](https://genai.owasp.org/llm-top-10/).

```bash
pip install "git+https://github.com/Davidfarouk/passive-income"
injectprobe demo        # no API key needed — attacks a deliberately vulnerable bot
```

The `demo` command runs 30 attacks against a built-in mock chatbot and writes a self-contained HTML report. You'll see categories like *system-prompt leakage*, *direct injection*, *indirect injection* and *data exfiltration*, each marked pass or fail, with the model's actual response and how to fix it.

## Testing a real model

```bash
export OPENAI_API_KEY=...
injectprobe run --target openai --model gpt-4o-mini --html report.html
```

It also speaks to Anthropic, any OpenAI-compatible server (Ollama, vLLM, Groq, OpenRouter), your own HTTP endpoint, or a Python function that runs your real prompt-assembly and RAG.

## Why canary-based detection matters

The clever part isn't the attacks — it's the detection. `injectprobe` plants a **random canary string** in the system prompt on every run. A leak is flagged even when the model tries to be sneaky about it: base64, hex, ROT13, reversed text, an acrostic poem, or the NATO alphabet. No LLM-as-judge, so no false confidence and no second API bill.

That means when `injectprobe` says your prompt leaked, it *actually* leaked — and when it says you're clean, that's a real signal.

## Testing what you actually ship

Testing the raw model tells you little. Your app has a system prompt, retrieval, and guardrails around it. Point `injectprobe` at the real thing:

```bash
injectprobe run --target http --url https://staging.example.com/chat \
  --body '{"message": "{prompt}"}' --response-path reply \
  --canary CANARY-YOUR-PLANTED-STRING
```

Plant that same canary in your staging system prompt, and any attack that extracts it fails the run.

## Put it in CI

```bash
injectprobe run --target http --url "$STAGING_URL" --canary "$CANARY" \
  --repeat 3 --fail-on high --junit results.xml
```

`--repeat 3` runs each attack three times (models are stochastic; a 1-in-3 jailbreak is still a jailbreak) and `--fail-on high` returns a non-zero exit code so a regression blocks the merge.

## Go deeper

The free core pack covers 30 attacks. If you're testing agents with tools, RAG pipelines, or want the full OWASP-mapped corpus, [**injectprobe Pro**](https://davidfarouk.gumroad.com/l/injectprobe-pro) adds 117 more attacks (147 total), a hardening playbook, and CI templates for $9.

Start with the free tool — `injectprobe demo` — and see where your app stands.
