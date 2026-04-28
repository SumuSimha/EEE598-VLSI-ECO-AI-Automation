# ECO Patch Report

- Status: `PATCH_APPLIED`
- Supported mode: `assign-level-combinational`
- Confidence: `90`
- Reason: Patch generated and verified against the golden baseline
- Details:
  - Patch generation will use Codex plus simulation-guided verification on suspicious outputs.
  - Reconstructed RTL summary: C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case05_logic_mux_sel\patched_netlist\reconstructed_rtl_summary.txt
  - Reconstructed RTL candidate: C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case05_logic_mux_sel\patched_netlist\reconstructed_rtl_candidate.v

## Bug Summary
- Bug type: `mux-select or conditional-expression mismatch`
- Affected outputs: mux_out
- Changed signals: mux_out
- Explanation: The buggy netlist differed from the golden design on 1 suspicious outputs and was patched within the supported assign-level-combinational flow.
- Ranked bug candidates:
  - mux_out (score=10)

## Changed Lines
- `insert` before 9-8 after 9-9
  - after:     
- `replace` before 11-11 after 12-12
  - before:     assign mux_out = sel ? b : a;
  - after:     assign mux_out = sel ? a : b;

## Verification
- Passed: `True`
- Summary: [SUCCESS] All vectors matched
C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case05_logic_mux_sel\tb\tb_logic_unit_a.v:58: $finish called at 3000 (1ps)

## Minimality
- Edit hunks: 2
- Changed line count: 3
- Changed signal count: 1
