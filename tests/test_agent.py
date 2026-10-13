from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from kozquloq.agent.diagnostics import DiagnosticAgent
from kozquloq.agent.tools import AuditTools

if TYPE_CHECKING:
    from kozquloq.storage.duckdb_store import Store


def test_mock_agent_runs_tools_and_reports(audited_store: Store) -> None:
    agent = DiagnosticAgent(audited_store, provider="mock")
    result = agent.run("why is the night slice degrading?")
    assert "health_summary" in result.tool_calls
    assert "slice_failures" in result.tool_calls
    assert "worst_samples" in result.tool_calls
    assert "## Diagnostic report" in result.report
    assert "ghost" in result.report.lower()


def test_run_sql_tool_readonly(audited_store: Store) -> None:
    tools = AuditTools(audited_store)
    rows = tools.dispatch("run_sql", {"sql": "SELECT COUNT(*) AS n FROM samples"})
    assert rows[0]["n"] == 8
    with pytest.raises(ValueError):
        tools.dispatch("run_sql", {"sql": "DROP TABLE samples"})
    with pytest.raises(ValueError):
        tools.dispatch("run_sql", {"sql": "INSERT INTO scenes VALUES ()"})


def test_tool_dispatch_all(audited_store: Store) -> None:
    tools = AuditTools(audited_store)
    assert tools.dispatch("health_summary")["grade"] in "ABCDF"
    assert isinstance(tools.dispatch("slice_failures"), list)
    assert len(tools.dispatch("worst_samples", {"n": 3})) <= 3
    assert tools.dispatch("category_breakdown")[0]["category"] == "vehicle.car"
    with pytest.raises(ValueError):
        tools.dispatch("nonexistent")
