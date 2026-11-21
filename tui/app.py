from __future__ import annotations

from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Static

from backend.app.services.optimizer_service import OptimizerService


class SmartGridApp(App):
    """A compact dashboard for viewing default schedules and classical optimizer baselines."""

    CSS = """
    Screen {
        layout: vertical;
        background: #0f172a;
        color: #e2e8f0;
    }

    #root {
        width: 100%;
        height: 100%;
        padding: 1 2;
    }

    #title {
        content-align: center middle;
        color: #93c5fd;
        text-style: bold;
        margin-bottom: 1;
    }

    #summary {
        height: auto;
        min-height: 8;
        border: round #334155;
        padding: 1 2;
        background: #111827;
    }

    #controls {
        height: auto;
        margin-top: 1;
        margin-bottom: 1;
    }

    Button {
        margin-right: 1;
    }

    DataTable {
        height: 12;
        border: round #475569;
    }

    #details {
        min-height: 8;
        max-height: 18;
        overflow-y: auto;
        border: round #475569;
        padding: 1 2;
        background: #111827;
    }
    """

    BINDINGS = [("q", "quit", "Quit"), ("r", "refresh", "Refresh")]

    def __init__(self) -> None:
        super().__init__()
        self.service = OptimizerService()
        self.results: list[Any] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="root"):
            yield Static("SmartGrid-QAOA Dashboard", id="title")
            yield Static("", id="summary")
            with Horizontal(id="controls"):
                yield Button("Run classical", id="classical")
                yield Button("Run QAOA", id="qaoa")
                yield Button("Refresh", id="refresh")
            yield DataTable(id="results")
            yield Static("", id="details")

    def on_mount(self) -> None:
        self._refresh_dashboard()

    def _refresh_dashboard(self) -> None:
        summary = self.service.scenario_summary()
        summary_lines = [
            f"Appliances: {summary.appliance_count}",
            f"Battery: {summary.battery_capacity_kwh:.1f} kWh",
            f"Grid limit: {summary.max_grid_kw:.1f} kW",
            f"Solar peak: {summary.solar_peak_kw:.1f} kW",
            f"Avg tariff: ${summary.average_tariff_per_kwh:.3f}/kWh",
            f"Default schedule valid: {'yes' if summary.default_schedule_valid else 'no'}",
            f"Default objective: {summary.default_objective:.2f}",
        ]
        self.query_one("#summary", Static).update("\n".join(summary_lines))

        self.results = self.service.run_classical_suite()
        table = self.query_one(DataTable)
        table.clear(columns=True)
        table.add_columns("Method", "Feasible", "Objective", "Cost", "Peak", "Runtime")
        for result in self.results:
            table.add_row(
                result.method,
                "yes" if result.feasible else "no",
                f"{result.objective_value:.2f}",
                f"{result.electricity_cost:.2f}",
                f"{result.peak_demand:.2f}",
                f"{result.runtime_seconds:.3f}s",
            )
        table.cursor_type = "row"
        if self.results:
            self._render_result(self.results[0])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "classical":
            self.results = self.service.run_classical_suite()
            self._render_table(self.results)
            if self.results:
                self._render_result(self.results[0])
        elif event.button.id == "qaoa":
            qaoa_result = self.service.run_qaoa_preview()
            if qaoa_result is None:
                self.query_one("#details", Static).update("QAOA is unavailable in this environment. Install qiskit-aer and retry.")
                return
            self.results = [qaoa_result]
            self._render_table([qaoa_result])
            self._render_result(qaoa_result)
        elif event.button.id == "refresh":
            self._refresh_dashboard()

    def _render_table(self, results: list[Any]) -> None:
        table = self.query_one(DataTable)
        table.clear(columns=True)
        table.add_columns("Method", "Feasible", "Objective", "Cost", "Peak", "Runtime")
        for result in results:
            table.add_row(
                result.method,
                "yes" if result.feasible else "no",
                f"{result.objective_value:.2f}",
                f"{result.electricity_cost:.2f}",
                f"{result.peak_demand:.2f}",
                f"{result.runtime_seconds:.3f}s",
            )

    def _render_result(self, result: Any) -> None:
        lines = [
            f"Method: {result.method}",
            f"Feasible: {'yes' if result.feasible else 'no'}",
            f"Objective: {result.objective_value:.2f}",
            f"Electricity cost: {result.electricity_cost:.2f}",
            f"Peak demand: {result.peak_demand:.2f}",
            f"Runtime: {result.runtime_seconds:.3f}s",
            "",
            "Active schedule:",
        ]
        schedule = getattr(result, "schedule", {}) or {}
        schedule_lines: list[str] = []
        for appliance_name in sorted(schedule):
            values = list(schedule.get(appliance_name, []))
            active_hours = [hour for hour, value in enumerate(values) if bool(value)]
            if active_hours:
                schedule_lines.append(f"- {appliance_name}: {active_hours}")
            else:
                schedule_lines.append(f"- {appliance_name}: []")
        if not schedule_lines:
            schedule_lines.append("- No active schedule data available.")
        lines.extend(schedule_lines)
        details = self.query_one("#details", Static)
        details.update("\n".join(lines))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if not self.results:
            return
        table = self.query_one(DataTable)
        index = getattr(event, "cursor_row", None)
        if index is None:
            index = getattr(event, "row_index", None)
        if index is None:
            row_key = getattr(event, "row_key", None)
            if row_key is not None and hasattr(table, "get_row_index"):
                try:
                    index = table.get_row_index(row_key)
                except Exception:
                    return
        if index is None:
            index = 0
        if 0 <= index < len(self.results):
            self._render_result(self.results[index])

    def action_refresh(self) -> None:
        self._refresh_dashboard()
