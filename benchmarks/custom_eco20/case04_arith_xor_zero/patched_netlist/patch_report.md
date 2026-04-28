# ECO Patch Report

- Status: `PATCH_APPLIED`
- Supported mode: `assign-level-combinational`
- Confidence: `90`
- Reason: Patch generated and verified against the golden baseline
- Details:
  - Patch generation will use Codex plus simulation-guided verification on suspicious outputs.
  - Reconstructed RTL summary: C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case04_arith_xor_zero\patched_netlist\reconstructed_rtl_summary.txt
  - Reconstructed RTL candidate: C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case04_arith_xor_zero\patched_netlist\reconstructed_rtl_candidate.v

## Bug Summary
- Bug type: `operator or datapath expression mismatch`
- Affected outputs: xor_out
- Changed signals: xor_out
- Explanation: The buggy netlist differed from the golden design on 1 suspicious outputs and was patched within the supported assign-level-combinational flow.
- Ranked bug candidates:
  - xor_out (score=8)

## Changed Lines
- `insert` before 7-6 after 7-7
  - after:     
- `replace` before 8-8 after 9-9
  - before:     assign xor_out = 8'h00;
  - after:     assign xor_out = a ^ b;

## Verification
- Passed: `True`
- Summary: [SUCCESS] All vectors matched
C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case04_arith_xor_zero\tb\tb_arith_unit_d.v:49: $finish called at 3000 (1ps)

## Minimality
- Edit hunks: 2
- Changed line count: 3
- Changed signal count: 1
