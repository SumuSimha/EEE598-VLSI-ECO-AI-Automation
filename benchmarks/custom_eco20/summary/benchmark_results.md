# Custom ECO20 Benchmark Results

- Total cases: 20
- Passed: 20
- Failed: 0
- Average runtime (s): 5.75
- Average strategy attempts: 2.6
- Average selected syntax attempts: 1.0
- Minimal patch case: case08_logic_const

| Case | Pass | Bug Type | Strategy Attempts | Minimality |
| --- | --- | --- | --- | --- |
| case01_arith_lower_add | yes | bit-slice or bus-range mismatch | 1 | h1/l4/s3 |
| case02_arith_xor_swap | yes | bit-slice or bus-range mismatch | 1 | h2/l4/s3 |
| case03_arith_sub | yes | operator or datapath expression mismatch | 3 | h2/l3/s1 |
| case04_arith_xor_zero | yes | operator or datapath expression mismatch | 3 | h2/l3/s1 |
| case05_logic_mux_sel | yes | mux-select or conditional-expression mismatch | 3 | h2/l3/s1 |
| case06_logic_or_and | yes | operator or datapath expression mismatch | 3 | h3/l3/s1 |
| case07_logic_nand_polarity | yes | inversion or polarity mismatch | 3 | h2/l3/s1 |
| case08_logic_const | yes | mux-select or conditional-expression mismatch | 3 | h1/l3/s1 |
| case09_compare_eq | yes | output-driver mismatch | 3 | h3/l3/s1 |
| case10_compare_gt | yes | output-driver mismatch | 3 | h2/l3/s1 |
| case11_compare_lt_swap | yes | output-driver mismatch | 3 | h2/l3/s1 |
| case12_compare_swap_outputs | yes | output-driver mismatch | 3 | h2/l5/s2 |
| case13_bitmix_upper_slice | yes | bit-slice or bus-range mismatch | 1 | h1/l3/s1 |
| case14_bitmix_mask_op | yes | bit-slice or bus-range mismatch | 3 | h3/l3/s1 |
| case15_bitmix_parity | yes | operator or datapath expression mismatch | 3 | h2/l3/s1 |
| case16_bitmix_invert | yes | inversion or polarity mismatch | 3 | h2/l3/s1 |
| case17_shift_left | yes | output-driver mismatch | 3 | h2/l3/s1 |
| case18_shift_rotate | yes | bit-slice or bus-range mismatch | 3 | h1/l3/s1 |
| case19_mux_three_way | yes | mux-select or conditional-expression mismatch | 3 | h1/l3/s1 |
| case20_checksum_slice | yes | bit-slice or bus-range mismatch | 1 | h1/l3/s1 |
