"""Thin LLM wrapper that records tokens and cost for every call."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0

    def add(self, other: "Usage") -> "Usage":
        return Usage(self.input_tokens + other.input_tokens, self.output_tokens + other.output_tokens,
                     self.latency_ms + other.latency_ms)

    @property
    def cost_usd(self) -> float:
        # Prices per million tokens come from the environment so they stay current.
        price_in = float(os.getenv("LLM_PRICE_INPUT_PER_MTOK", "0"))
        price_out = float(os.getenv("LLM_PRICE_OUTPUT_PER_MTOK", "0"))
        return (self.input_tokens * price_in + self.output_tokens * price_out) / 1_000_000


def complete(system: str, prompt: str, max_tokens: int = 800) -> tuple[str, Usage]:
    """One model call; returns the text and its usage."""
    import anthropic

    client = anthropic.Anthropic()
    model = os.getenv("DESK_COPILOT_MODEL", "claude-sonnet-5-5")
    start = time.perf_counter()
    resp = client.messages.create(model=model, max_tokens=max_tokens, system=system,
                                  messages=[{"role": "user", "content": prompt}])
    elapsed = (time.perf_counter() - start) * 1000
    text = "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")
    return text, Usage(resp.usage.input_tokens, resp.usage.output_tokens, elapsed)
