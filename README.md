# SmartGrid-QAOA

SmartGrid-QAOA is a compact research prototype for residential microgrid scheduling that combines:

- a shared backend energy model for demand, tariffs, solar, and battery behavior
- classical baselines (MILP, greedy, simulated annealing)
- a standard QAOA pipeline implemented with Qiskit Aer
- a small terminal dashboard and a simple web UI for local experimentation

The project is intentionally modest and honest about scale. It is designed for small benchmark instances rather than large-scale industrial deployments.

## Project goals

- Model a realistic residential demand-scheduling scenario with appliance windows and cost trade-offs
- Provide a common backend service layer shared by the terminal UI and website
- Compare classical optimization against a compact QAOA prototype under the same benchmark conditions
- Avoid unsupported quantum advantage claims by making feasibility and runtime transparent

## Architecture

- `backend/energy/` — shared microgrid and scheduling model
- `backend/optimization/classical/` — MILP, greedy, simulated annealing baselines
- `backend/optimization/qaoa/` — QAOA standard and research variants
- `backend/app/services/` — shared service abstraction for TUI/API usage
- `backend/app/api/` — FastAPI routes and schemas
- `tui/` — terminal dashboard built with Textual
- `frontend/` — static website dashboard for browser-based inspection
- `backend/tests/` — unit and integration coverage

## Quick start

### Python environment

From the project root:

```bash
python -m pip install -r requirements.txt
```

### Terminal dashboard

```bash
python tui.py
```

### Web application

```bash
python web.py
```

Then visit:

```text
http://localhost:8000/
```

### Benchmark runner

```bash
python benchmark.py
```

## API endpoints

The FastAPI backend exposes:

- `GET /api/health`
- `GET /api/summary`
- `GET /api/default-schedule`
- `POST /api/optimize`
- `POST /api/benchmark`
- `POST /api/validate`

## Benchmarking approach

The benchmark layer compares methods using the same compact scenario and several seeds. It reports:

- feasible rate
- objective mean
- best objective value
- runtime mean

This provides a transparent research comparison rather than a claim of quantum superiority.

## Validation

Run the test suite with:

```bash
python -m unittest discover -s backend/tests -v
```

## Important constraints and limitations

- The problem remains a prototype, not a production scheduler.
- QAOA is run on a reduced scheduling instance to stay computationally realistic.
- Battery dynamics are handled in the classical model and validation layer, while the QAOA path focuses on the scheduling decision structure.
- The benchmarking is designed to produce transparent, reproducible evidence, not to overstate the maturity of the quantum approach.

## Phase summary

- Phase 0: design and formulation
- Phase 1: core model and energy logic
- Phase 2: classical optimization baselines
- Phase 3: standard QAOA pipeline
- Phase 4: research QAOA variants
- Phase 5: terminal dashboard
- Phase 6: website and backend API
- Phase 7: benchmarking and comparison
- Phase 8: final documentation and integration cleanup
