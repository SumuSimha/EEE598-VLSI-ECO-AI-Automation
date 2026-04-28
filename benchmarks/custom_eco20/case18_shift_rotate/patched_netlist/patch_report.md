# ECO Patch Report

- Status: `PATCH_APPLIED`
- Supported mode: `assign-level-combinational`
- Confidence: `90`
- Reason: Patch generated and verified against the golden baseline
- Details:
  - Patch generation will use Codex plus simulation-guided verification on suspicious outputs.
  - Reconstructed RTL summary: C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case18_shift_rotate\patched_netlist\reconstructed_rtl_summary.txt
  - Reconstructed RTL candidate: C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case18_shift_rotate\patched_netlist\reconstructed_rtl_candidate.v

## Bug Summary
- Bug type: `bit-slice or bus-range mismatch`
- Affected outputs: rotl1, rotr1
- Changed signals: rotl1
- Explanation: The buggy netlist differed from the golden design on 2 suspicious outputs and was patched within the supported assign-level-combinational flow.
- Ranked bug candidates:
  - rotl1 (score=13)
  - rotr1 (score=13)

## Changed Lines
- `replace` before 6-6 after 6-7
  - before:     assign rotl1 = {data[0], data[7:1]};
  - after:     
  - after:     assign rotl1 = {data[6:0], data[7]};

## Verification
- Passed: `True`
- Summary: [SUCCESS] All vectors matched
C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case18_shift_rotate\tb\tb_shift_unit_b.v:44: $finish called at 3000 (1ps)

## Minimality
- Edit hunks: 1
- Changed line count: 3
- Changed signal count: 1
