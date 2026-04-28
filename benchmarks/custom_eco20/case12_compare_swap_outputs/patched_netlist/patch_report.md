# ECO Patch Report

- Status: `PATCH_APPLIED`
- Supported mode: `assign-level-combinational`
- Confidence: `90`
- Reason: Patch generated and verified against the golden baseline
- Details:
  - Patch generation will use Codex plus simulation-guided verification on suspicious outputs.
  - Reconstructed RTL summary: C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case12_compare_swap_outputs\patched_netlist\reconstructed_rtl_summary.txt
  - Reconstructed RTL candidate: C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case12_compare_swap_outputs\patched_netlist\reconstructed_rtl_candidate.v

## Bug Summary
- Bug type: `output-driver mismatch`
- Affected outputs: gt, lt
- Changed signals: gt, lt
- Explanation: The buggy netlist differed from the golden design on 2 suspicious outputs and was patched within the supported assign-level-combinational flow.
- Ranked bug candidates:
  - gt (score=9)
  - lt (score=9)

## Changed Lines
- `replace` before 8-8 after 8-8
  - before:     assign gt = a < b;
  - after:     
- `replace` before 10-10 after 10-11
  - before:     assign lt = a > b;
  - after:     assign gt = a > b;
  - after:     assign lt = a < b;

## Verification
- Passed: `True`
- Summary: [SUCCESS] All vectors matched
C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case12_compare_swap_outputs\tb\tb_compare_unit_d.v:53: $finish called at 3000 (1ps)

## Minimality
- Edit hunks: 2
- Changed line count: 5
- Changed signal count: 2
