# ECO Patch Report

- Status: `PATCH_APPLIED`
- Supported mode: `assign-level-combinational`
- Confidence: `90`
- Reason: Patch generated and verified against the golden baseline
- Details:
  - Patch generation will use Codex plus simulation-guided verification on suspicious outputs.
  - Reconstructed RTL summary: C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case17_shift_left\patched_netlist\reconstructed_rtl_summary.txt
  - Reconstructed RTL candidate: C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case17_shift_left\patched_netlist\reconstructed_rtl_candidate.v

## Bug Summary
- Bug type: `output-driver mismatch`
- Affected outputs: left_shift
- Changed signals: left_shift
- Explanation: The buggy netlist differed from the golden design on 1 suspicious outputs and was patched within the supported assign-level-combinational flow.
- Ranked bug candidates:
  - left_shift (score=10)

## Changed Lines
- `replace` before 7-7 after 7-7
  - before:     assign left_shift = data >> sh;
  - after:     
- `insert` before 9-8 after 9-9
  - after:     assign left_shift = data << sh;

## Verification
- Passed: `True`
- Summary: [SUCCESS] All vectors matched
C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case17_shift_left\tb\tb_shift_unit_a.v:49: $finish called at 3000 (1ps)

## Minimality
- Edit hunks: 2
- Changed line count: 3
- Changed signal count: 1
