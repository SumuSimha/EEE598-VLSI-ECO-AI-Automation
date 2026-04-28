# ECO Patch Report

- Status: `PATCH_APPLIED`
- Supported mode: `assign-level-combinational`
- Confidence: `90`
- Reason: Patch generated and verified against the golden baseline
- Details:
  - Patch generation will use Codex plus simulation-guided verification on suspicious outputs.
  - Reconstructed RTL summary: C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case03_arith_sub\patched_netlist\reconstructed_rtl_summary.txt
  - Reconstructed RTL candidate: C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case03_arith_sub\patched_netlist\reconstructed_rtl_candidate.v

## Bug Summary
- Bug type: `operator or datapath expression mismatch`
- Affected outputs: sum
- Changed signals: sum
- Explanation: The buggy netlist differed from the golden design on 1 suspicious outputs and was patched within the supported assign-level-combinational flow.
- Ranked bug candidates:
  - sum (score=9)

## Changed Lines
- `replace` before 7-7 after 7-7
  - before:     assign sum = a - b;
  - after:     
- `insert` before 9-8 after 9-9
  - after:     assign sum = a + b;

## Verification
- Passed: `True`
- Summary: [SUCCESS] All vectors matched
C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case03_arith_sub\tb\tb_arith_unit_c.v:49: $finish called at 3000 (1ps)

## Minimality
- Edit hunks: 2
- Changed line count: 3
- Changed signal count: 1
