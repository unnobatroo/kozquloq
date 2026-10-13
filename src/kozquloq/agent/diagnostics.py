"""Agentic diagnostic engine: NL query -> tool calls -> Markdown report."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from kozquloq.agent.providers import LLMProvider, get_provider
from kozquloq.agent.tools import AuditTools

if TYPE_CHECKING:
    from kozquloq.storage.duckdb_store import Store

_SYSTEM = (
    "You are a data-quality diagnostician for autonomous driving datasets. "
    "Use the provided tools to query the audit store, then produce a concise "
    "Markdown root-cause report: findings, affected slices, recommended actions."
)


@dataclass
class DiagnosticResult:
    report: str
    tool_calls: list[str] = field(default_factory=list)


class DiagnosticAgent:
    def __init__(self, store: Store, provider: str | LLMProvider = "mock") -> None:
        self.tools = AuditTools(store)
        self.provider = get_provider(provider) if isinstance(provider, str) else provider

    def run(self, query: str, max_steps: int = 4) -> DiagnosticResult:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": query},
        ]
        for _ in range(max_steps):
            resp = self.provider.complete(messages)
            if not resp.tool_calls:
                return DiagnosticResult(
                    report=resp.content or "(empty report)",
                    tool_calls=list(self.tools.calls),
                )
            messages.append(
                {
                    "role": "assistant",
                    "content": resp.content or "",
                    "tool_calls": [c.name for c in resp.tool_calls],
                }
            )
            for call in resp.tool_calls:
                try:
                    result = self.tools.dispatch(call.name, call.args)
                except Exception as e:  # report tool errors back to the model
                    result = {"error": str(e)}
                messages.append({"role": "tool", "name": call.name, "content": json.dumps(result)})
        return DiagnosticResult(
            report="Diagnostic agent hit max_steps without a final report.",
            tool_calls=list(self.tools.calls),
        )
