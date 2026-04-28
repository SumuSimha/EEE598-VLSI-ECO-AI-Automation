# ECO Patch Report

- Status: `PATCH_APPLIED`
- Supported mode: `assign-level-combinational`
- Confidence: `90`
- Reason: Patch generated and verified against the golden baseline
- Details:
  - Patch generation will use Codex plus simulation-guided verification on suspicious outputs.
  - Reconstructed RTL summary: C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case02_arith_xor_swap\patched_netlist\reconstructed_rtl_summary.txt
  - Reconstructed RTL candidate: C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case02_arith_xor_swap\patched_netlist\reconstructed_rtl_candidate.v

## Bug Summary
- Bug type: `bit-slice or bus-range mismatch`
- Affected outputs: sum, xor_out
- Changed signals: xor_out, xor_out[3:0], xor_out[7:4]
- Explanation: The buggy netlist differed from the golden design on 2 suspicious outputs and was patched within the supported assign-level-combinational flow.
- Ranked bug candidates:
  - xor_out (score=5)
  - sum (score=5)

## Changed Lines
- `insert` before 7-6 after 7-7
  - after:     
- `replace` before 8-9 after 9-9
  - before:     assign xor_out[3:0] = a[7:4] ^ b[7:4];
  - before:     assign xor_out[7:4] = a[3:0] ^ b[3:0];
  - after:     assign xor_out = a ^ b;

## Verification
- Passed: `True`
- Summary: [SUCCESS] All vectors matched
C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case02_arith_xor_swap\tb\tb_arith_unit_b.v:49: $finish called at 3000 (1ps)

## Minimality
- Edit hunks: 2
- Changed line count: 4
- Changed signal count: 3
