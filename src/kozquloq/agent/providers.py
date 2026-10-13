"""LLM providers for the diagnostic agent.

`mock` is deterministic and offline: it issues a fixed plan of tool calls,
then renders a Markdown root-cause report from the real tool results.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMProvider(Protocol):
    def complete(self, messages: list[dict[str, Any]]) -> LLMResponse: ...


class MockProvider:
    """Offline provider: first turn plans tools, second turn writes the report."""

    _PLAN = [
        ToolCall("health_summary"),
        ToolCall("slice_failures"),
        ToolCall("worst_samples", {"n": 5}),
        ToolCall("category_breakdown"),
    ]

    def complete(self, messages: list[dict[str, Any]]) -> LLMResponse:
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        if not tool_msgs:
            return LLMResponse(tool_calls=list(self._PLAN))
        return LLMResponse(content=self._render(messages, tool_msgs))

    def _render(self, messages: list[dict[str, Any]], tool_msgs: list[dict[str, Any]]) -> str:
        query = next((m["content"] for m in messages if m.get("role") == "user"), "")
        data = {m["name"]: json.loads(m["content"]) for m in tool_msgs}
        h = data.get("health_summary", {})
        slices = data.get("slice_failures", [])
        worst = data.get("worst_samples", [])
        cats = data.get("category_breakdown", [])

        lines = [
            "## Diagnostic report",
            "",
            f"**Query:** {query}",
            "",
            f"**Dataset health: {h.get('grade', '?')}** — "
            f"{h.get('frames', 0)} frames, {h.get('annotations', 0)} annotations, "
            f"{h.get('flagged', 0)} flagged ({h.get('failure_pct', 0)}%).",
            "",
            "### Findings",
            *self._findings(h),
        ]

        if slices:
            lines += ["", "### Worst slices (weather / time / category)"]
            for s in slices[:5]:
                lines.append(
                    f"- {s['weather']} / {s['time_of_day']} / {s['category']}: "
                    f"{s['failure_rate_pct']}% failure ({s['ghost_labels_count']} ghosts, "
                    f"{s['kinematic_outliers_count']} kinematic)"
                )
        if worst:
            lines += ["", "### Most anomalous frames"]
            for w in worst[:5]:
                lines.append(
                    f"- `{w['sample_token']}` — severity {w['max_severity']}, "
                    f"{w['ghosts']} ghosts, {w['kinematic_outliers']} kinematic outliers"
                )
        if cats:
            lines += ["", "### Category severity ranking"]
            for c in cats[:5]:
                lines.append(
                    f"- {c['category']}: avg severity {c['avg_severity']} "
                    f"({c['ghosts']} ghosts / {c['kin_outliers']} kinematic of {c['n']})"
                )
        return "\n".join(lines)

    @staticmethod
    def _findings(h: dict[str, Any]) -> list[str]:
        lines = []
        if h.get("ghosts"):
            lines.append(
                f"- **{h['ghosts']} ghost label(s)**: annotations with zero LiDAR "
                "returns inside 35 m — likely over-labeling or dropped lidar packets."
            )
        if h.get("kinematic_outliers"):
            lines.append(
                f"- **{h['kinematic_outliers']} kinematic outlier(s)**: non-physical "
                "velocity/acceleration between keyframes — tracking dropouts or "
                "instance-ID swaps."
            )
        if h.get("scale_unstable"):
            lines.append(
                f"- **{h['scale_unstable']} scale-unstable box(es)**: rigid-object "
                "volume changed >15% — annotation regression."
            )
        if h.get("underexposed_frames"):
            lines.append(
                f"- **{h['underexposed_frames']} underexposed frame(s)**: check "
                "camera exposure/gain for those timestamps."
            )
        if h.get("drift_frames"):
            lines.append(
                f"- **{h['drift_frames']} frame(s) with geometric drift**: lidar "
                "returns land outside reprojected box footprints — check "
                "lidar→camera calibration."
            )
        return lines or ["- No anomalies detected; dataset is clean."]


class OpenAIProvider:
    """Thin tool-calling loop over the OpenAI API (lazy-imported)."""

    def __init__(self, model: str = "gpt-4o-mini") -> None:
        try:
            import openai
        except ImportError as e:
            raise RuntimeError("pip install openai to use provider='openai'") from e
        self._client = openai.OpenAI()
        self._model = model

    def complete(self, messages: list[dict[str, Any]]) -> LLMResponse:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "run_sql",
                    "description": "Read-only SELECT against scenes/samples/annotation_audits/view_slice_failure_rates",
                    "parameters": {
                        "type": "object",
                        "properties": {"sql": {"type": "string"}},
                        "required": ["sql"],
                    },
                },
            }
        ]
        resp = self._client.chat.completions.create(
            model=self._model, messages=messages, tools=tools
        )
        msg = resp.choices[0].message
        calls = [
            ToolCall(c.function.name, json.loads(c.function.arguments or "{}"))
            for c in (msg.tool_calls or [])
        ]
        return LLMResponse(content=msg.content, tool_calls=calls)


def get_provider(name: str) -> LLMProvider:
    if name == "mock":
        return MockProvider()
    if name == "openai":
        return OpenAIProvider()
    raise ValueError(f"unknown provider: {name} (mock | openai)")
