# ECO Patch Report

- Status: `PATCH_APPLIED`
- Supported mode: `assign-level-combinational`
- Confidence: `90`
- Reason: Patch generated and verified against the golden baseline
- Details:
  - Patch generation will use Codex plus simulation-guided verification on suspicious outputs.
  - Reconstructed RTL summary: C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case20_checksum_slice\patched_netlist\reconstructed_rtl_summary.txt
  - Reconstructed RTL candidate: C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case20_checksum_slice\patched_netlist\reconstructed_rtl_candidate.v

## Bug Summary
- Bug type: `bit-slice or bus-range mismatch`
- Affected outputs: checksum, folded
- Changed signals: checksum
- Explanation: The buggy netlist differed from the golden design on 2 suspicious outputs and was patched within the supported assign-level-combinational flow.
- Ranked bug candidates:
  - checksum (score=4)
  - folded (score=4)

## Changed Lines
- `replace` before 6-6 after 6-7
  - before:     assign checksum = data[15:8] + data[15:8];
  - after:     
  - after:     assign checksum = data[15:8] + data[7:0];

## Verification
- Passed: `True`
- Summary: [SUCCESS] All vectors matched
C:\Users\sumuk\OneDrive\Desktop\Auto_VLSI\benchmarks\custom_eco20\case20_checksum_slice\tb\tb_checksum_unit_a.v:44: $finish called at 3000 (1ps)

## Minimality
- Edit hunks: 1
- Changed line count: 3
- Changed signal count: 1
