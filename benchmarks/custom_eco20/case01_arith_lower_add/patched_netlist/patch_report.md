# ECO Patch Report

- Status: `PATCH_APPLIED`
- Supported mode: `assign-level-combinational`
- Confidence: `90`
- Reason: Patch generated and verified against the golden baseline
- Details:
  - Patch generation will use Codex plus simulation-guided verification on suspicious outputs.
  - Reconstructed RTL summary: C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case01_arith_lower_add\patched_netlist\reconstructed_rtl_summary.txt
  - Reconstructed RTL candidate: C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case01_arith_lower_add\patched_netlist\reconstructed_rtl_candidate.v

## Bug Summary
- Bug type: `bit-slice or bus-range mismatch`
- Affected outputs: sum, xor_out
- Changed signals: sum, sum[3:0], sum[7:4]
- Explanation: The buggy netlist differed from the golden design on 2 suspicious outputs and was patched within the supported assign-level-combinational flow.
- Ranked bug candidates:
  - sum (score=5)
  - xor_out (score=5)

## Changed Lines
- `replace` before 7-8 after 7-8
  - before:     assign sum[3:0] = a[3:0] & b[3:0];
  - before:     assign sum[7:4] = a[7:4] + b[7:4];
  - after:     
  - after:     assign sum = a + b;

## Verification
- Passed: `True`
- Summary: [SUCCESS] All vectors matched
C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case01_arith_lower_add\tb\tb_arith_unit_a.v:49: $finish called at 3000 (1ps)

## Minimality
- Edit hunks: 1
- Changed line count: 4
- Changed signal count: 3
