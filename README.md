# Automated ECO Agent - Phase 3

This repository contains the Phase 3 submission for an AI-assisted ECO repair flow for Verilog designs. The tool performs feasibility analysis, bug localization, candidate patch generation, simulation-based verification, and structured reporting.

The main Phase 3 benchmark is `benchmarks/custom_eco20`, which contains 20 buggy Verilog repair cases. The benchmark runner lets the grader run all 20 cases or any selected subset.

## Quick Start For Grading

Build the Docker image:

```bash
docker compose build
```

Run the quick root example in analysis-only mode:

```bash
docker compose up
```

List all 20 benchmark cases:

```bash
docker compose run --rm eco-agent python tools/run_custom_benchmark.py --list
```

Run all 20 benchmark cases:

```bash
docker compose run --rm eco-benchmark
```

Run selected cases only:

```bash
docker compose run --rm eco-agent python tools/run_custom_benchmark.py 1
docker compose run --rm eco-agent python tools/run_custom_benchmark.py 1 5 20
docker compose run --rm eco-agent python tools/run_custom_benchmark.py case05_logic_mux_sel case20_checksum_slice
```

The benchmark runner uses the deterministic heuristic executor, so the 20-case benchmark does not require Codex login.

## Expected Results

The latest checked Phase 3 benchmark result was:

```text
Total cases: 20
Passed: 20
Failed: 0
Average strategy attempts: 2.6
Average selected syntax attempts: 1.0
```

Summary files are written to:

```text
benchmarks/custom_eco20/summary/benchmark_results.json
benchmarks/custom_eco20/summary/benchmark_results.csv
benchmarks/custom_eco20/summary/benchmark_results.md
```

Each selected benchmark case also generates a local `patched_netlist/` directory inside that case. Those generated folders are ignored by Git because they can be regenerated with the Docker commands above.

## Repository Contents

```text
ECO_Agent.py                         Main ECO agent
run_simulation.py                    Thin wrapper around ECO_Agent.py
tools/run_custom_benchmark.py        Batch runner for the 20 Phase 3 cases
benchmarks/custom_eco20/             20 benchmark cases
golden_rtl/                          Root example golden RTL
buggy_netlist/                       Root example buggy implementation
tb/                                  Root example testbench
lib/                                 Optional library models
Dockerfile                           Portable tool environment
docker-compose.yml                   Quick-run and benchmark services
EEE525_Project2_Phase3_Report.pdf    Phase 3 report
```

## Benchmark Case Layout

Each custom ECO20 benchmark case follows this structure:

```text
caseXX_name/
|-- golden_rtl/
|   `-- correct_design.v
|-- buggy_netlist/
|   `-- buggy_design.v
|-- tb/
|   `-- self_checking_testbench.v
`-- patched_netlist/                 Generated after running the tool
```

The 20 buggy files are under:

```text
benchmarks/custom_eco20/case*/buggy_netlist/
```

## Running Without Docker

Install requirements:

```bash
python -m pip install -r requirements.txt
```

Required local tools:

```text
Python 3.10+
Icarus Verilog: iverilog and vvp in PATH
```

Run the quick root example:

```bash
python run_simulation.py --check-only
```

Run all 20 benchmark cases:

```bash
python tools/run_custom_benchmark.py --all
```

Run selected benchmark cases:

```bash
python tools/run_custom_benchmark.py 1 5 20
```

## ECO Agent Input Modes

Auto-discovery from a project root:

```bash
python ECO_Agent.py --project-root path/to/project_root
```

Explicit input files:

```bash
python ECO_Agent.py \
  --golden-file path/to/golden.v \
  --buggy-file path/to/buggy.v \
  --tb-file path/to/tb.v \
  --lib-dir path/to/lib
```

Analysis-only mode:

```bash
python ECO_Agent.py --check-only --project-root path/to/project_root
```

Print the required layout:

```bash
python ECO_Agent.py --print-layout
```

## Outputs

For each run, the generated output directory may contain:

```text
feasibility_report.json
feasibility_report.md
reconstructed_rtl_summary.txt
reconstructed_rtl_candidate.v
patch_report.json
patch_report.md
<top>_patched.v
repair_session_log.txt
```

The reports explain whether repair was possible, which signals were suspicious, what strategy was selected, whether simulation passed, and how large the patch was.

## AI Usage

The project supports Codex-backed patch generation and auto-testbench generation, but the submitted ECO20 benchmark path uses the deterministic heuristic executor for reproducible grading. Codex login is only needed when running options that explicitly use the Codex executor or auto-testbench generation.

## Scope And Limitations

Best-supported cases:

- Assign-level combinational designs
- Some combinational procedural designs
- Benchmark-style reconstruction when `buggy_rtl/` is available
- Wrapper-only fallback for some gate-level designs
- Limited single-clock sequential classification

Known limitations:

- Correctness is based on visible simulation testbenches, not full formal equivalence.
- General sequential ECO repair is not fully implemented.
- Gate-level ECO repair depends on having usable standard-cell simulation models.
- Generated `patched_netlist/` folders are intentionally not committed on the clean branch.
