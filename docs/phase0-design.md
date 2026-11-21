# SmartGrid-QAOA — Phase 0 Technical Design

## 1. Workspace status
The current workspace was inspected before any code changes were made. No existing project files, repositories, or prior source trees were present in this working directory, so no project artifacts required preservation.

This means the design below establishes the project foundation from a clean slate, while keeping the architecture explicit and aligned with the requested phased delivery plan.

---

## 2. Problem definition
The objective is to schedule a small residential microgrid over a 24-hour horizon while minimizing total cost and maintaining acceptable consumer comfort. The system includes:

- household appliances with fixed energy demand and preferred operating windows
- rooftop solar generation
- battery charge/discharge behavior
- grid import from the utility
- time-of-use tariff schedule
- optional EV charging requirements
- aggregate grid-power limit and peak-demand penalties

The system must balance operational feasibility with economic efficiency. The optimization targets are:

- minimize electricity purchase cost
- reduce demand peaks that trigger expensive tariff events or grid stress
- respect user comfort windows and appliance duration constraints
- satisfy battery and grid limits
- produce a schedule that can be used by both a terminal UI and a website from the same backend logic

The design uses a discrete-time formulation, which is well-suited for a QAOA/QUBO pipeline while also supporting exact classical baseline solvers such as MILP.

---

## 3. Mathematical formulation
### 3.1 Time horizon and loads
Let:
- T = 24 hourly time slots
- N = number of appliances (initially 5–8, configurable)
- i ∈ {1, ..., N} index appliances
- t ∈ {1, ..., T} index hours

For appliance i:
- p_i = power demand in kW during an active hour
- d_i = required active duration in hours
- a_i = earliest allowed hour
- b_i = latest allowed hour
- r_{i,t} = preference weight for using appliance i at time t

The discrete-hour schedule variable is:
- x_{i,t} ∈ {0,1}
- x_{i,t} = 1 if appliance i is active in hour t, otherwise 0

The appliance must be active a fixed number of hours inside its feasible window:

Σ_{t=a_i}^{b_i} x_{i,t} = d_i

and for t outside the window:

x_{i,t} = 0

This makes the model easy to encode in binary variables and keeps the optimization tractable for the initial research scenario.

### 3.2 Electricity balance
Let:
- g_t = grid import at hour t (kWh or kW over a 1-hour interval)
- s_t = solar generation at hour t
- b_t^+ = battery charging power at hour t
- b_t^- = battery discharging power at hour t
- E_t = total demand from all scheduled appliances and optional EV load at hour t

The hour-by-hour power balance is:

E_t + b_t^+ = s_t + g_t + b_t^- + L_t

where L_t represents any fixed non-flexible load or demand not controlled by the optimizer.

A practical simplified formulation for the research prototype is:

D_t = Σ_i p_i x_{i,t} + EV_t + L_t 

g_t + s_t + b_t^- - b_t^+ - D_t = 0

with battery constraints:

0 ≤ SOC_t ≤ SOC_max

SOC_{t+1} = SOC_t + η_ch b_t^+ - (1/η_dis) b_t^-

b_t^+ ≤ B_max_ch

b_t^- ≤ B_max_dis

This is easier to include in the exact MILP baseline and can be approximated in the QAOA formulation by keeping battery decisions classical and only optimizing appliance scheduling while battery state is derived from the schedule or treated as a small penalty term.

### 3.3 Objective function
The baseline objective is:

J = α * C_grid + β * P_peak + γ * C_discomfort

where:
- C_grid = Σ_t λ_t g_t
- λ_t = electricity tariff at hour t
- P_peak = peak demand penalty
- C_discomfort = discomfort cost from schedules outside preferred times

The discomfort term is:

C_discomfort = Σ_{i,t} w_{i,t} x_{i,t}

with a larger penalty when the appliance is scheduled in a low-preference or inconvenient hour.

The peak-demand penalty is modeled as:

P_peak = Σ_t max(0, D_t - P_cap)^2

or its smooth approximation for the QUBO model.

This makes the objective align with the requirement to minimize energy cost while reducing grid stress and preserving user comfort.

---

## 4. Decision variables
### 4.1 Binary variables
For the main QAOA formulation, use binary schedule variables:

x_{i,t} ∈ {0,1}

This directly maps to the qubit count.

### 4.2 Supporting variables for MILP
The exact classical solver can include auxiliary continuous variables for:
- grid import g_t
- battery charge/discharge b_t^+, b_t^-
- battery state-of-charge SOC_t
- peak-load slack variables

These are not required for the initial QAOA implementation; they remain classical and are either projected out or absorbed into the objective penalty terms.

### 4.3 Qubit count estimate
For a small instance with:
- N = 6 appliances
- T = 24 hours
- x_{i,t} variables only

qubits = N * T = 6 * 24 = 144

This is manageable for a simulator but large enough to challenge practical variational optimization. To keep the initial prototype computationally honest, the design should start with smaller instances, for example:
- 4 appliances × 12 hours = 48 qubits
- 5 appliances × 12 hours = 60 qubits
- 6 appliances × 12 hours = 72 qubits

This is the recommended initial experimental scale before scaling to 24-hour schedules.

---

## 5. Constraints
The main constraints are:

1. Appliance-duration feasibility
   Σ_{t=a_i}^{b_i} x_{i,t} = d_i

2. Window restriction
   x_{i,t} = 0 if t < a_i or t > b_i

3. Grid capacity / aggregate demand cap
   Σ_i p_i x_{i,t} + EV_t + L_t ≤ P_grid_cap + slack_t

4. Battery feasibility
   SOC_min ≤ SOC_t ≤ SOC_max
   0 ≤ b_t^+ ≤ B_max_ch
   0 ≤ b_t^- ≤ B_max_dis

5. Optional EV charging rule
   Σ_t x_EV,t = d_EV
   charging hours respect time windows

6. Peak-demand reduction surrogate
   a quadratic penalty on total demand above a threshold is used instead of a hard max in the QAOA formulation

These are physically meaningful and line up with the energy-management problem definition.

---

## 6. QUBO conversion
The QAOA pipeline requires a QUBO/Ising formulation. The design below is mathematically consistent for the initial simplified objective.

### 6.1 Linear cost term
The electricity purchase cost from load schedule is:

C_grid = Σ_t λ_t g_t

Given an aggregate demand model, a simplified approximation is:

C_grid ≈ Σ_{i,t} λ_t p_i x_{i,t}

This is a linear term in x_{i,t}, which directly becomes a QUBO linear contribution.

### 6.2 Discomfort penalty
The discomfort penalty is also linear:

C_discomfort = Σ_{i,t} w_{i,t} x_{i,t}

This contributes directly to the QUBO objective.

### 6.3 Peak-demand penalty
The key nonlinear term is:

P_peak = Σ_t (D_t - P_cap)^2

where:

D_t = Σ_i p_i x_{i,t} + EV_t + L_t

Expanding:

P_peak = Σ_t [D_t^2 - 2P_cap D_t + P_cap^2]

Since each x_{i,t} is binary, D_t^2 contains linear terms and quadratic cross-terms:

D_t^2 = Σ_i p_i^2 x_{i,t} + 2 Σ_{i<j} p_i p_j x_{i,t} x_{j,t}

This means the peak penalty contributes both:
- linear terms in x_{i,t}
- quadratic terms x_{i,t} x_{j,t} for appliances active in the same hour

This is the correct QUBO behavior for a discrete-time scheduling model, and it naturally captures peak overlap.

### 6.4 Duration constraints in QUBO
For each appliance i, enforce the exact active-hour count as a penalty:

M_i (Σ_{t=a_i}^{b_i} x_{i,t} - d_i)^2

Expanding this yields:
- linear terms from x_{i,t}
- quadratic cross-terms x_{i,t} x_{i,t'} for different hours of the same appliance

Because x_{i,t}^2 = x_{i,t} for binary variables, the expression stays quadratic. This is a standard and valid QUBO encoding of the cardinality constraint.

### 6.5 Suitability and limitations
This design is mathematically sound for a compact initial benchmark. The main limitation is that it does not yet include a full battery-SOC dynamic in the QUBO. Instead, the exact battery dynamics remain in the MILP and in the classical post-processing layer, while the QAOA model focuses on the schedule decision problem. This is a deliberate simplification to avoid generating an impractically large QUBO and to stay true to the requirement of a manageable initial model.

---

## 7. QAOA circuit design
### 7.1 Encoding
The qubits correspond one-to-one with the binary scheduling variables x_{i,t}. This is a straightforward binary encoding that keeps the problem faithful to the original scheduling decisions.

For a 6-appliance, 24-hour model, the circuit uses 144 qubits. This is large for QAOA, but feasible for simulator-based research with shallow depth and small benchmarks.

### 7.2 Cost Hamiltonian
The QUBO objective Q(x) becomes an Ising Hamiltonian through the standard transformation:

z_j ∈ {+1, -1} where x_j = (1 - z_j)/2

Then:

H_C = Σ_j h_j Z_j + Σ_{j<k} J_{jk} Z_j Z_k + const

This cost Hamiltonian is implemented as parameterized phase-separation operators.

### 7.3 Mixer Hamiltonian
The standard mixer is:

H_M = Σ_j X_j

which produces the usual QAOA mixer:

U_M(β) = exp(-i β H_M)

For the initial standard QAOA implementation, this is valid and trusted.

### 7.4 Circuit depth
Use a shallow depth p such as:
- p = 1, 2, 3 for small experiments
- p up to 5 for moderate prototypes

The choice of p must remain small enough to avoid unrealistic simulator runtime while still allowing parameter convergence.

### 7.5 Measurement and decoding
After executing the QAOA circuit, measurement bitstrings are sampled and decoded back into schedule variables:

bitstring b = b_1 ... b_m

x_{i,t} = b_k for the corresponding qubit index k

The resulting schedule is then validated against:
- appliance duration counts
- preferred windows
- aggregate demand cap
- battery feasibility (if included in the post-processing check)

If a measurement is infeasible, it is rejected or penalized in the objective evaluation.

---

## 8. Constraint-aware mixer feasibility
The project explicitly requires a research-oriented mixer that is not purely penalty-driven. The correct design must respect a feasible subspace.

### 8.1 What can be preserved exactly
A valid and practical constraint-aware mixer for this model is a cardinality-preserving swap mixer on the schedule of each appliance.

For a fixed appliance i with required duration d_i, the number of active slots is fixed. The mixer acts by swapping a pair of bits:

x_{i,t_1} = 1, x_{i,t_2} = 0

→

x_{i,t_1} = 0, x_{i,t_2} = 1

while preserving the total number of active slots in the allowed window.

This is a valid feasible-state operation because it keeps:

Σ_t x_{i,t} = d_i

It is mathematically appropriate for the discrete-time appliance-duration constraint and ensures the mixer does not violate the per-appliance schedule cardinality.

### 8.2 What remains penalty-based
The aggregate demand cap, peak-demand penalty, and battery-state feasibility are not as naturally preserved by a small local mixer because the appliance schedules can interact across different appliances and hours in a coupled way.

Therefore:
- per-appliance duration constraints: preserved by a cardinality-aware mixer
- aggregate load and peak constraints: still handled by QUBO penalties
- battery and grid constraints: handled by validation and penalty terms or a classical repair step

This is a mathematically honest and practically defensible approach for the initial project.

### 8.3 Why not enforce a full feasible-state mixer for all constraints?
A globally feasible mixer for the full household scheduling problem would need to preserve all simultaneous constraints, including aggregate load, battery dynamics, and user-window preferences, which is substantially more complex. Such a mixer is not a simple one- or two-qubit operation and would require a carefully designed problem-specific quantum walk over a highly constrained subspace. That is beyond the scope of the initial prototype and is an explicit research extension rather than a required baseline.

---

## 9. Fourier-based parameter initialization
The project requirement calls for Fourier-based initialization inspired by Zhou et al. (2020), with parameter transfer between shallow and deeper QAOA circuits.

### 9.1 Strategy
The design is:

1. optimize a shallow QAOA circuit with depth p0 (for example p0 = 2 or 3)
2. record the converged parameters γ^(p0), β^(p0)
3. expand the parameter vector to a larger depth p > p0 using a Fourier interpolation scheme
4. use the interpolated values as a warm start for the deeper optimization

This is a sensible way to reduce optimization instability while preserving the structure of the variational ansatz.

### 9.2 Practical implementation
Use a low-depth Fourier basis, for example:

γ_k ≈ Σ_m a_m sin(2π m k / (p+1))
β_k ≈ Σ_m b_m cos(2π m k / (p+1))

with coefficients estimated from the lower-depth optimization or generated from a bounded heuristic.

The important point is not the precise closed-form of the coefficients, but the flow:
- optimize at low depth
- transfer parameters to higher depth
- compare with random initialization

This enables a fair research comparison between:
- random initialization
- Fourier-based initialization
- transferred parameter warm starts

---

## 10. Classical baselines
The project must compare QAOA against classical methods that are mathematically valid and independent.

### 10.1 Exact MILP
Use a discrete-time MILP with binary appliance variables and linearized battery and grid constraints.

This is the reference optimizer for small instance sizes and provides a strong ground truth.

### 10.2 Greedy scheduler
Construct a feasible schedule greedily by ordering appliances by:
- urgency (deadline proximity)
- cost sensitivity
- discomfort penalty
- renewable availability

Apply local improvement steps until the schedule is feasible.

### 10.3 Simulated annealing
Represent a full schedule as a vector of discrete assignments, then perform:
- random swaps or bit flips
- acceptance based on energy objective and constraint penalties
- temperature annealing schedule

This baseline is suitable for evaluating heuristic improvement without the full complexity of a MILP solver.

---

## 11. Shared TUI and website architecture
The user request explicitly requires both interfaces to use the same optimization backend and data model.

### 11.1 Proposed directory structure
smartgrid-qaoa/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── routes.py
│   │   │   └── schemas.py
│   │   └── services/
│   │       ├── optimizer_service.py
│   │       ├── dataset_service.py
│   │       └── comparison_service.py
│   ├── energy/
│   │   ├── appliances.py
│   │   ├── battery.py
│   │   ├── solar.py
│   │   ├── tariff.py
│   │   └── energy_model.py
│   ├── optimization/
│   │   ├── formulation.py
│   │   ├── qubo.py
│   │   ├── hamiltonian.py
│   │   ├── classical/
│   │   │   ├── milp.py
│   │   │   ├── greedy.py
│   │   │   └── annealing.py
│   │   └── qaoa/
│   │       ├── standard.py
│   │       ├── mixers.py
│   │       ├── fourier.py
│   │       ├── enhanced.py
│   │       └── circuit.py
│   ├── evaluation/
│   │   ├── metrics.py
│   │   ├── feasibility.py
│   │   └── comparison.py
│   ├── data/
│   └── tests/
├── tui/
│   ├── main.py
│   ├── app.py
│   ├── screens/
│   └── services/
├── frontend/
│   ├── src/
│   └── package.json
├── experiments/
│   ├── benchmarks/
│   └── results/
├── docs/
├── README.md
├── requirements.txt
└── docker-compose.yml

### 11.2 Backend contract
The backend will expose endpoints for:
- configuration generation
- optimization execution
- algorithm selection
- result retrieval
- comparison runs
- CSV/JSON export

The TUI can either:
- call the backend through FastAPI, or
- call the core Python service layer directly for local execution

The preferred design for this project is:
- shared service layer for all optimization logic
- FastAPI endpoint wrapper for the website and any external clients
- optional direct Python invocation for the TUI if local responsiveness is preferred

This avoids any accidental duplication of the optimizer logic.

---

## 12. Testing strategy
Testing is mandatory and must be aligned with the mathematical components.

### 12.1 Core unit tests
- appliance duration constraints
- feasibility validation for schedules
- solar generation and battery charge balance with small synthetic scenarios
- objective computation under cost and discomfort weights
- QUBO coefficient expansion and sanity checks
- Hamiltonian conversion from QUBO to Ising form

### 12.2 Classical baseline tests
- exact MILP optimizer on a small instance
- greedy schedule feasibility validation
- simulated annealing acceptance behavior on a toy schedule

### 12.3 QAOA tests
- circuit construction on a small instance
- parameter shape validation
- measurement decoding from bitstrings into schedule variables
- feasibility checks after decoding
- comparison between random and Fourier initialization on the same small instance

### 12.4 Regression expectations
The tests should be designed to fail for:
- incorrect duration counts
- invalid scheduling windows
- broken electricity-balance assumptions
- objective mismatches between classical and quantum-decoded schedules
- invalid QUBO-to-Ising conversion

---

## 13. Risks and computational limitations
### 13.1 Qubit scaling
A full 24-hour, 6-appliance schedule can require 144+ qubits in the direct binary encoding. This is workable in a simulator at very shallow depth but will not remain scalable for deeper QAOA experiments.

### 13.2 Constraint complexity
The full QUBO with grid, battery, and peak-demand dynamics becomes significantly more coupled than the simple appliance-scheduling formulation. This is why the initial research design uses a focused schedule model and keeps battery dynamics as a classical post-processing/repair layer.

### 13.3 Variational training instability
QAOA parameter optimization is sensitive to the energy landscape, especially for large QUBO instances. Fourier warm-starts, shallow-depth optimization, and random seeding are necessary to keep the prototype stable.

### 13.4 Feasibility rate
A naive QAOA circuit may often sample infeasible schedules. This is expected unless a feasible-state mixer or explicit repair mechanism is used. The project must therefore include explicit validity checks and avoid claiming improved results without measured feasibility.

### 13.5 Quantum advantage claims
The project explicitly disallows unproven quantum advantage claims. The research plan must compare QAOA with classical baselines using the same benchmark sets and report objective values, feasibility rates, and runtime transparently.

---

## 14. Recommended initial benchmark instance
To keep the first phase mathematically and computationally honest, use a benchmark with:
- 4 to 6 appliances
- 12-hour scheduling window or full 24-hour window with restricted active-hours
- one battery
- solar profile for a representative day
- fixed TOU tariffs
- 1 EV load option

This yields a tractable problem size for the first research iterations while still being realistic for a residential microgrid.

---

## 15. Execution roadmap
### Phase 0: Approval and design
- problem framing and mathematics complete
- architecture defined
- no implementation yet

### Phase 1: Core energy model
- appliance model
- synthetic dataset generation
- battery and solar modeling
- constraint validation
- CLI demonstration

### Phase 2: Classical optimization
- MILP baseline
- greedy baseline
- simulated annealing

### Phase 3: Standard QAOA
- QUBO conversion
- Ising Hamiltonian
- circuit execution
- decoding and evaluation

### Phase 4: Research improvements
- constraint-aware mixer
- Fourier initialization
- enhanced QAOA

### Phase 5–8: TUI, website, benchmarks, documentation
- shared backend integration
- interactive interfaces
- experiments and final documentation

---

## 16. Final recommendation
The design above is the right starting point for Phase 0 because it is:

- mathematically grounded
- realistic for a small residential microgrid
- compatible with both classical and quantum optimization
- suitable for a shared backend architecture between TUI and website
- explicit about where feasibility is enforced directly versus where penalties are used

This model is intentionally modest and honest, which makes the research objective achievable without pretending the architecture is more scalable than it is.

The next step is review and approval of this design. Once approved, Phase 1 can begin with the core energy model and test harness.
