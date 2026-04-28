# Automated ECO Agent

This project implements a generic AI-assisted ECO flow for supported Verilog repair cases. The tool performs feasibility analysis, bug localization, Codex-driven patch generation, simulation-based verification, and structured reporting.

## Scope

Best-supported classes:
- Assign-level combinational designs
- Some combinational procedural designs
- Benchmark-style standard-cell reconstruction cases when `buggy_rtl/` is available
- Wrapper-only fallback for some gate-level designs
- Limited single-clock sequential classification and Phase 3 plumbing

Current outputs:
- `feasibility_report.json`
- `feasibility_report.md`
- `reconstructed_rtl_summary.txt`
- `reconstructed_rtl_candidate.v`
- `patch_report.json`
- `patch_report.md`
- patched Verilog outputs in `patched_netlist/`

## Recommended Project Layout

```text
project_root/
|-- golden_rtl/
|   |-- top.v
|   `-- support_files...
|-- buggy_netlist/
|   |-- top_netlist.v
|   `-- support_files...
|-- tb/
|   `-- tb_top.v
|-- lib/
|   `-- standard_cells.v
|-- buggy_rtl/                  # optional, used for reconstruction mode
|   `-- candidate_buggy_rtl...
`-- patched_netlist/            # auto-generated output directory
```

Optional batch-friendly organization:

```text
project_root/
`-- cases/
    |-- case_01/
    |   |-- golden_rtl/
    |   |-- buggy_netlist/
    |   |-- tb/
    |   `-- lib/
    `-- case_02/
        |-- golden_rtl/
        |-- buggy_netlist/
        |-- tb/
        `-- lib/
```

Recommended generated output layout:

```text
patched_netlist/
|-- feasibility_report.json
|-- feasibility_report.md
|-- reconstructed_rtl_summary.txt
|-- reconstructed_rtl_candidate.v
|-- patch_report.json
|-- patch_report.md
|-- <top>_patched.v
`-- logs/                      # optional future extension for batch runs
```

## Input Modes

### 1. Auto-discovery from a clean project root

```powershell
python ECO_Agent.py --project-root C:\path\to\project_root
```

This mode expects the recommended folder layout above.

### 2. Explicit file paths

```powershell
python ECO_Agent.py `
  --golden-file C:\path\to\golden.v `
  --buggy-file C:\path\to\buggy.v `
  --tb-file C:\path\to\tb.v `
  --lib-dir C:\path\to\lib
```

Use this when the user does not want to follow the recommended folder layout.

### 3. Analysis-only mode

```powershell
python ECO_Agent.py --check-only --project-root C:\path\to\project_root
```

This runs feasibility analysis and reconstruction artifact generation without invoking Codex for patch generation.

### 4. Auto-testbench generation

```powershell
python ECO_Agent.py `
  --golden-file C:\path\to\golden.v `
  --buggy-file C:\path\to\buggy.v `
  --auto-testbench `
  --lib-dir C:\path\to\lib
```

This uses Codex CLI to generate a self-checking testbench from the golden RTL.

## Requirements

- Python 3.10+
- Icarus Verilog with `iverilog` and `vvp` in `PATH`
- Codex CLI installed and authenticated for patch generation or auto-testbench generation
- Python dependencies from [requirements.txt](/C:/Users/sumuk/OneDrive/Desktop/Auto_VLSI/requirements.txt)

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Docker

Portable execution assets are included:
- [Dockerfile](/C:/Users/sumuk/OneDrive/Desktop/Auto_VLSI/Dockerfile)
- [docker-compose.yml](/C:/Users/sumuk/OneDrive/Desktop/Auto_VLSI/docker-compose.yml)

Default quick feasibility run on the root example:

```powershell
docker compose up --build
```

Build the image once before running custom benchmark commands directly:

```powershell
docker compose build
```

Run all 20 custom ECO benchmark cases:

```powershell
docker compose run --rm eco-benchmark
```

List available benchmark cases:

```powershell
docker compose run --rm eco-agent python tools/run_custom_benchmark.py --list
```

Run whichever benchmark cases you want by number or case name:

```powershell
docker compose run --rm eco-agent python tools/run_custom_benchmark.py 1
docker compose run --rm eco-agent python tools/run_custom_benchmark.py 1 5 20
docker compose run --rm eco-agent python tools/run_custom_benchmark.py case05_logic_mux_sel case20_checksum_slice
```

Benchmark results are written to:

```text
benchmarks/custom_eco20/summary/benchmark_results.json
benchmarks/custom_eco20/summary/benchmark_results.csv
benchmarks/custom_eco20/summary/benchmark_results.md
```

Each selected case also gets its own generated `patched_netlist/` directory. The benchmark runner cleans selected case outputs before rerunning by default; pass `--keep-outputs` if you want to preserve prior generated files. For Codex-backed patch generation, the container still needs Codex authentication configured by the user. The 20-case benchmark uses the deterministic heuristic executor, so it does not require Codex login.

## Built-in Layout Help

Users can ask the tool to print the required generic project structure:

```powershell
python ECO_Agent.py --print-layout
```

## Notes

- The tool is generic in interface, but not universal in repair power.
- It is strongest on supported combinational and benchmark-style cases.
- Reports are designed to tell the user when a repair is possible, wrapper-only, or out of scope.
