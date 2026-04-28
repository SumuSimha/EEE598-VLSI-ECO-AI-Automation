# ECO Patch Report

- Status: `PATCH_APPLIED`
- Supported mode: `assign-level-combinational`
- Confidence: `90`
- Reason: Patch generated and verified against the golden baseline
- Details:
  - Patch generation will use Codex plus simulation-guided verification on suspicious outputs.
  - Reconstructed RTL summary: C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case15_bitmix_parity\patched_netlist\reconstructed_rtl_summary.txt
  - Reconstructed RTL candidate: C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case15_bitmix_parity\patched_netlist\reconstructed_rtl_candidate.v

## Bug Summary
- Bug type: `operator or datapath expression mismatch`
- Affected outputs: parity
- Changed signals: parity
- Explanation: The buggy netlist differed from the golden design on 1 suspicious outputs and was patched within the supported assign-level-combinational flow.
- Ranked bug candidates:
  - parity (score=9)

## Changed Lines
- `insert` before 8-7 after 8-8
  - after:     
- `replace` before 10-10 after 11-11
  - before:     assign parity = ^mask;
  - after:     assign parity = ^data;

## Verification
- Passed: `True`
- Summary: [SUCCESS] All vectors matched
C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case15_bitmix_parity\tb\tb_bitmix_unit_c.v:53: $finish called at 3000 (1ps)

## Minimality
- Edit hunks: 2
- Changed line count: 3
- Changed signal count: 1
