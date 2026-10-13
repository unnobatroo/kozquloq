"""Interactive Rich REPL: conversational diagnostics + slash commands (§5.3)."""

from __future__ import annotations

import webbrowser
from pathlib import Path

from rich.markdown import Markdown
from rich.prompt import Prompt

from kozquloq.agent.diagnostics import DiagnosticAgent
from kozquloq.cli.console import console, health_table, slices_table, worst_table
from kozquloq.storage import views
from kozquloq.storage.duckdb_store import Store
from kozquloq.visualization.report_generator import render_report

_HELP = (
    "[bold]Commands[/]: /summary, /slices, /worst, /report, /exit\n"
    "Anything else is sent to the diagnostic agent."
)


def _open_report(store: Store, report_path: str) -> None:
    out = render_report(store, Path(report_path))
    console.print(f"Report written to {out.resolve()}")
    webbrowser.open(out.resolve().as_uri())


def run_repl(db_path: str, report_path: str = "audit_report.html") -> None:
    store = Store(db_path)
    agent = DiagnosticAgent(store, provider="mock")
    console.print("[bold cyan]kozquloq chat[/] — " + _HELP)

    commands = {
        "/summary": lambda: console.print(health_table(views.health_summary(store))),
        "/slices": lambda: console.print(slices_table(views.slice_failure_rates(store))),
        "/worst": lambda: console.print(worst_table(views.worst_samples(store))),
        "/report": lambda: _open_report(store, report_path),
        "/help": lambda: console.print(_HELP),
    }

    while True:
        try:
            text = Prompt.ask("[bold green]kozquloq>[/]").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            continue
        if text in ("/exit", "/quit"):
            break
        elif text in commands:
            commands[text]()
        elif text.startswith("/"):
            console.print(f"[red]Unknown command {text}[/] — /help for commands.")
        else:
            result = agent.run(text)
            console.print(Markdown(result.report))

    store.close()
    console.print("[dim]bye.[/]")
