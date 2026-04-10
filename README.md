# EEE598-VLSI-ECO-AI-Automation
Autonomous AI-driven system for VLSI bug localization and ECO patch generation. Features closed-loop simulation feedback using Icarus Verilog and LLM-based reasoning for netlist repair.

PROJECT OVERVIEW
This project implements an Automated Engineering Change Order (ECO) flow using
an AI-driven "Orchestrator" layer. The tool identifies functional discrepancies
between a Golden RTL reference and a Buggy Netlist, autonomously generates a
Verilog patch, and verifies the fix using Icarus Verilog.

The core innovation lies in the Hybrid Orchestration Strategy, which bypasses
AI sandbox limitations by using a Python-based execution layer to implement the
AI's logical reasoning on the physical file system.

2. PROJECT STRUCTURE
Auto_VLSI/
|-- golden_rtl/          Reference Verilog files (Correct Logic)
|-- buggy_netlist/       Gate-level netlists containing logical errors
|-- patched_netlist/     Output directory for AI-generated repairs
|-- tb/                  Testbenches for functional verification
|-- lib/                 Standard Cell Library definitions (.v)
|-- ECO_Agent.py         The main Python Orchestrator script
|-- final_repair_log.txt  Automatically generated execution logs
`-- README.txt           You are here!

3. FEATURES
- Semantic Logic Diffing: The AI analyzes the functional intent of the code
  rather than just text differences.
- Autonomous Patching: Automatically corrects common VLSI errors such as
  bit-slice swaps and incorrect gate mappings.
- Closed-Loop Verification: Integrates with iverilog and vvp to ensure the
  patched netlist matches the golden reference before finalizing.
- Hybrid Execution: Combines high-level AI reasoning with a robust Python
  backend to handle file I/O and toolchain execution safely.

4. GETTING STARTED

Prerequisites:
- Python 3.8+
- Icarus Verilog: Ensure 'iverilog' and 'vvp' are added to your System PATH.
- Codex CLI: Installed and authenticated via your research/API provider.

Installation & Setup:
1. Clone this repository to your local machine (e.g., C:\Auto_VLSI).
2. Ensure your directory structure matches the "Project Structure" section.
3. Place your buggy files in buggy_netlist/ and the reference in golden_rtl/.

Running the ECO Flow:
Simply run the orchestrator script from the project root:
Command: python ECO_Agent.py

5. HOW IT WORKS
- Analysis Phase: The Orchestrator sends the Golden and Buggy files to the AI.
- Diagnostic Phase: The Agent identifies specific logic failures (e.g., "Sum
  logic using XOR instead of ADD").
- Repair Phase: The Agent provides a corrected Verilog module wrapped in unique
  markers (---FIXED_CODE_START---).
- Implementation: Python extracts the code, cleans any Markdown formatting, and
  saves it to the patched_netlist/ folder.
- Verification: The script triggers iverilog. If the testbench prints
  [SUCCESS], the repair is confirmed.

6. EXAMPLE LOG OUTPUT
[STATUS] Invoking AI Agent for Logic Analysis...
[SUCCESS] Python extracted and saved the patch.
[STATUS] Running Icarus Verilog Simulation...
=== SIMULATION RESULTS ===
Starting Simulation...
[SUCCESS] Matches Golden RTL
==========================

7. CHALLENGES & FUTURE SCOPE
- Sandbox Security: Current AI CLIs often enforce read-only environments. This
  project solves this via Python bridging.
- Next Step (Phase 3): Implementing a Dockerized environment to encapsulate the
  EDA toolchain (iverilog, Yosys) for full portability across different
  operating systems.
