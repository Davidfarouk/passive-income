"""injectprobe: prompt-injection and system-prompt-leak testing for LLM apps.

Zero dependencies. Point it at any OpenAI-compatible, Anthropic, HTTP or
Python target and it fires a pack of attacks, then detects leaks with
per-run canary tokens (including base64/hex/reversed/spelled-out leaks).
"""

__version__ = "0.1.0"
