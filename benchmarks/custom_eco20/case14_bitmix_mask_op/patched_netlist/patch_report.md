# ECO Patch Report

- Status: `PATCH_APPLIED`
- Supported mode: `assign-level-combinational`
- Confidence: `90`
- Reason: Patch generated and verified against the golden baseline
- Details:
  - Patch generation will use Codex plus simulation-guided verification on suspicious outputs.
  - Reconstructed RTL summary: C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case14_bitmix_mask_op\patched_netlist\reconstructed_rtl_summary.txt
  - Reconstructed RTL candidate: C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case14_bitmix_mask_op\patched_netlist\reconstructed_rtl_candidate.v

## Bug Summary
- Bug type: `bit-slice or bus-range mismatch`
- Affected outputs: masked_lo
- Changed signals: masked_lo
- Explanation: The buggy netlist differed from the golden design on 1 suspicious outputs and was patched within the supported assign-level-combinational flow.
- Ranked bug candidates:
  - masked_lo (score=9)

## Changed Lines
- `insert` before 8-7 after 8-8
  - after:     
- `delete` before 9-9 after 10-9
  - before:     assign masked_lo = data[7:0] | mask[7:0];
- `insert` before 11-10 after 11-11
  - after:     assign masked_lo = data[7:0] & mask[7:0];

## Verification
- Passed: `True`
- Summary: [SUCCESS] All vectors matched
C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case14_bitmix_mask_op\tb\tb_bitmix_unit_b.v:53: $finish called at 3000 (1ps)

## Minimality
- Edit hunks: 3
- Changed line count: 3
- Changed signal count: 1
