from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BENCH_ROOT = ROOT / "benchmarks" / "custom_eco20"


def decl_to_width(decl: str) -> str:
    return decl.split()[0] if decl.startswith("[") else ""


def reg_decl(decl: str, name: str) -> str:
    width = decl_to_width(decl)
    return f"reg {width} {name};".replace("  ", " ")


def wire_decl(decl: str, name: str) -> str:
    width = decl_to_width(decl)
    return f"wire {width} {name};".replace("  ", " ")


def literal(value: str) -> str:
    return value


def write_case(case: dict) -> None:
    case_root = BENCH_ROOT / case["name"]
    if case_root.exists():
        shutil.rmtree(case_root)

    golden_dir = case_root / "golden_rtl"
    buggy_dir = case_root / "buggy_netlist"
    tb_dir = case_root / "tb"
    golden_dir.mkdir(parents=True, exist_ok=True)
    buggy_dir.mkdir(parents=True, exist_ok=True)
    tb_dir.mkdir(parents=True, exist_ok=True)

    module = case["module"]
    golden_path = golden_dir / f"{module}.v"
    buggy_path = buggy_dir / f"{module}_bug.v"
    tb_path = tb_dir / f"tb_{module}.v"

    port_lines = []
    all_ports = [("input", name, decl) for name, decl in case["inputs"]] + [
        ("output", name, decl) for name, decl in case["outputs"]
    ]
    for index, (direction, name, decl) in enumerate(all_ports):
        suffix = "," if index < len(all_ports) - 1 else ""
        line = f"    {direction} {decl} {name}" if decl else f"    {direction} {name}"
        port_lines.append(f"{line}{suffix}")

    golden_assigns = "\n".join(f"    assign {lhs} = {rhs};" for lhs, rhs in case["golden_assigns"])
    buggy_assigns = "\n".join(f"    assign {lhs} = {rhs};" for lhs, rhs in case["buggy_assigns"])

    module_header = "\n".join(port_lines)
    golden_source = f"""module {module} (
{module_header}
);
{golden_assigns}
endmodule
"""
    buggy_source = f"""module {module} (
{module_header}
);
{buggy_assigns}
endmodule
"""
    golden_path.write_text(golden_source, encoding="utf-8")
    buggy_path.write_text(buggy_source, encoding="utf-8")

    input_regs = "\n    ".join(reg_decl(decl, name) for name, decl in case["inputs"])
    output_wires = "\n    ".join(wire_decl(decl, name) for name, decl in case["outputs"])
    expected_wires = "\n    ".join(
        wire_decl(decl, f"expected_{name}") for name, decl in case["outputs"]
    )
    expected_assigns = "\n    ".join(
        f"assign expected_{lhs} = {rhs};" for lhs, rhs in case["golden_assigns"]
    )
    port_map = ",\n        ".join(f".{name}({name})" for name, _ in case["inputs"] + case["outputs"])

    vector_lines = []
    for idx, vector in enumerate(case["vectors"], start=1):
        for signal, value in vector.items():
            vector_lines.append(f"        {signal} = {literal(value)};")
        vector_lines.append("        #1;")
        checks = " || ".join(f"{name} !== expected_{name}" for name, _ in case["outputs"])
        vector_lines.append(f"        if ({checks}) begin")
        vector_lines.append("            mismatches = mismatches + 1;")
        display_parts = [f'"Case {idx} mismatch"']
        for name, _ in case["outputs"]:
            display_parts.append(f'" {name}=%h expected=%h"')
        display_fmt = ", ".join(display_parts)
        display_args = ", ".join(
            item for pair in ((name, f"expected_{name}") for name, _ in case["outputs"]) for item in pair
        )
        vector_lines.append(f"            $display({display_fmt}, {display_args});")
        vector_lines.append("        end")

    tb_source = f"""`timescale 1ns/1ps

module tb_{module};
    integer mismatches;
    {input_regs}
    {output_wires}
    {expected_wires}

    {expected_assigns}

    {module} uut (
        {port_map}
    );

    initial begin
        mismatches = 0;
{chr(10).join(vector_lines)}
        if (mismatches == 0)
            $display("[SUCCESS] All vectors matched");
        else
            $display("[MISMATCH] Total mismatches: %0d", mismatches);
        $finish;
    end
endmodule
"""
    tb_path.write_text(tb_source, encoding="utf-8")


CASES = [
    {
        "name": "case01_arith_lower_add",
        "module": "arith_unit_a",
        "inputs": [("a", "[7:0]"), ("b", "[7:0]")],
        "outputs": [("sum", "[7:0]"), ("xor_out", "[7:0]")],
        "golden_assigns": [("sum", "a + b"), ("xor_out", "a ^ b")],
        "buggy_assigns": [("sum[3:0]", "a[3:0] & b[3:0]"), ("sum[7:4]", "a[7:4] + b[7:4]"), ("xor_out", "a ^ b")],
        "vectors": [{"a": "8'h0F", "b": "8'h01"}, {"a": "8'hA5", "b": "8'h3C"}, {"a": "8'h80", "b": "8'h11"}],
    },
    {
        "name": "case02_arith_xor_swap",
        "module": "arith_unit_b",
        "inputs": [("a", "[7:0]"), ("b", "[7:0]")],
        "outputs": [("sum", "[7:0]"), ("xor_out", "[7:0]")],
        "golden_assigns": [("sum", "a + b"), ("xor_out", "a ^ b")],
        "buggy_assigns": [("sum", "a + b"), ("xor_out[3:0]", "a[7:4] ^ b[7:4]"), ("xor_out[7:4]", "a[3:0] ^ b[3:0]")],
        "vectors": [{"a": "8'hAA", "b": "8'h55"}, {"a": "8'h3C", "b": "8'hC3"}, {"a": "8'hF0", "b": "8'h0F"}],
    },
    {
        "name": "case03_arith_sub",
        "module": "arith_unit_c",
        "inputs": [("a", "[7:0]"), ("b", "[7:0]")],
        "outputs": [("sum", "[7:0]"), ("xor_out", "[7:0]")],
        "golden_assigns": [("sum", "a + b"), ("xor_out", "a ^ b")],
        "buggy_assigns": [("sum", "a - b"), ("xor_out", "a ^ b")],
        "vectors": [{"a": "8'h20", "b": "8'h03"}, {"a": "8'h05", "b": "8'h09"}, {"a": "8'hFF", "b": "8'h01"}],
    },
    {
        "name": "case04_arith_xor_zero",
        "module": "arith_unit_d",
        "inputs": [("a", "[7:0]"), ("b", "[7:0]")],
        "outputs": [("sum", "[7:0]"), ("xor_out", "[7:0]")],
        "golden_assigns": [("sum", "a + b"), ("xor_out", "a ^ b")],
        "buggy_assigns": [("sum", "a + b"), ("xor_out", "8'h00")],
        "vectors": [{"a": "8'h0A", "b": "8'h0A"}, {"a": "8'h5A", "b": "8'hA5"}, {"a": "8'h11", "b": "8'h22"}],
    },
    {
        "name": "case05_logic_mux_sel",
        "module": "logic_unit_a",
        "inputs": [("a", "[7:0]"), ("b", "[7:0]"), ("sel", "")],
        "outputs": [("and_out", "[7:0]"), ("or_out", "[7:0]"), ("mux_out", "[7:0]")],
        "golden_assigns": [("and_out", "a & b"), ("or_out", "a | b"), ("mux_out", "sel ? a : b")],
        "buggy_assigns": [("and_out", "a & b"), ("or_out", "a | b"), ("mux_out", "sel ? b : a")],
        "vectors": [{"a": "8'h0F", "b": "8'hF0", "sel": "1'b0"}, {"a": "8'h12", "b": "8'h34", "sel": "1'b1"}, {"a": "8'hAA", "b": "8'h55", "sel": "1'b1"}],
    },
    {
        "name": "case06_logic_or_and",
        "module": "logic_unit_b",
        "inputs": [("a", "[7:0]"), ("b", "[7:0]"), ("sel", "")],
        "outputs": [("and_out", "[7:0]"), ("or_out", "[7:0]"), ("mux_out", "[7:0]")],
        "golden_assigns": [("and_out", "a & b"), ("or_out", "a | b"), ("mux_out", "sel ? a : b")],
        "buggy_assigns": [("and_out", "a & b"), ("or_out", "a & b"), ("mux_out", "sel ? a : b")],
        "vectors": [{"a": "8'h0C", "b": "8'h03", "sel": "1'b0"}, {"a": "8'hF0", "b": "8'h0F", "sel": "1'b1"}, {"a": "8'h33", "b": "8'h55", "sel": "1'b0"}],
    },
    {
        "name": "case07_logic_nand_polarity",
        "module": "logic_unit_c",
        "inputs": [("a", "[7:0]"), ("b", "[7:0]")],
        "outputs": [("nand_out", "[7:0]"), ("xor_out", "[7:0]")],
        "golden_assigns": [("nand_out", "~(a & b)"), ("xor_out", "a ^ b")],
        "buggy_assigns": [("nand_out", "a & b"), ("xor_out", "a ^ b")],
        "vectors": [{"a": "8'hFF", "b": "8'h0F"}, {"a": "8'h81", "b": "8'h18"}, {"a": "8'h55", "b": "8'hAA"}],
    },
    {
        "name": "case08_logic_const",
        "module": "logic_unit_d",
        "inputs": [("a", "[7:0]"), ("b", "[7:0]"), ("sel", "")],
        "outputs": [("pass_out", "[7:0]"), ("mix_out", "[7:0]")],
        "golden_assigns": [("pass_out", "sel ? a : b"), ("mix_out", "(a & b) | ({8{sel}} & a)")],
        "buggy_assigns": [("pass_out", "8'hFF"), ("mix_out", "(a & b) | ({8{sel}} & a)")],
        "vectors": [{"a": "8'h01", "b": "8'h10", "sel": "1'b0"}, {"a": "8'hC3", "b": "8'h3C", "sel": "1'b1"}, {"a": "8'h5A", "b": "8'hA5", "sel": "1'b0"}],
    },
    {
        "name": "case09_compare_eq",
        "module": "compare_unit_a",
        "inputs": [("a", "[7:0]"), ("b", "[7:0]")],
        "outputs": [("gt", ""), ("eq", ""), ("lt", "")],
        "golden_assigns": [("gt", "a > b"), ("eq", "a == b"), ("lt", "a < b")],
        "buggy_assigns": [("gt", "a > b"), ("eq", "a != b"), ("lt", "a < b")],
        "vectors": [{"a": "8'h02", "b": "8'h02"}, {"a": "8'h10", "b": "8'h01"}, {"a": "8'h01", "b": "8'h10"}],
    },
    {
        "name": "case10_compare_gt",
        "module": "compare_unit_b",
        "inputs": [("a", "[7:0]"), ("b", "[7:0]")],
        "outputs": [("gt", ""), ("eq", ""), ("lt", "")],
        "golden_assigns": [("gt", "a > b"), ("eq", "a == b"), ("lt", "a < b")],
        "buggy_assigns": [("gt", "a >= b"), ("eq", "a == b"), ("lt", "a < b")],
        "vectors": [{"a": "8'h08", "b": "8'h08"}, {"a": "8'h09", "b": "8'h08"}, {"a": "8'h07", "b": "8'h08"}],
    },
    {
        "name": "case11_compare_lt_swap",
        "module": "compare_unit_c",
        "inputs": [("a", "[7:0]"), ("b", "[7:0]")],
        "outputs": [("gt", ""), ("eq", ""), ("lt", "")],
        "golden_assigns": [("gt", "a > b"), ("eq", "a == b"), ("lt", "a < b")],
        "buggy_assigns": [("gt", "a > b"), ("eq", "a == b"), ("lt", "a > b")],
        "vectors": [{"a": "8'h0A", "b": "8'h0B"}, {"a": "8'h10", "b": "8'h03"}, {"a": "8'h04", "b": "8'h04"}],
    },
    {
        "name": "case12_compare_swap_outputs",
        "module": "compare_unit_d",
        "inputs": [("a", "[7:0]"), ("b", "[7:0]")],
        "outputs": [("gt", ""), ("eq", ""), ("lt", "")],
        "golden_assigns": [("gt", "a > b"), ("eq", "a == b"), ("lt", "a < b")],
        "buggy_assigns": [("gt", "a < b"), ("eq", "a == b"), ("lt", "a > b")],
        "vectors": [{"a": "8'hFE", "b": "8'h01"}, {"a": "8'h01", "b": "8'hFE"}, {"a": "8'h33", "b": "8'h33"}],
    },
    {
        "name": "case13_bitmix_upper_slice",
        "module": "bitmix_unit_a",
        "inputs": [("data", "[15:0]"), ("mask", "[15:0]")],
        "outputs": [("upper_xor", "[7:0]"), ("masked_lo", "[7:0]"), ("parity", "")],
        "golden_assigns": [("upper_xor", "data[15:8] ^ mask[15:8]"), ("masked_lo", "data[7:0] & mask[7:0]"), ("parity", "^data")],
        "buggy_assigns": [("upper_xor", "data[7:0] ^ mask[7:0]"), ("masked_lo", "data[7:0] & mask[7:0]"), ("parity", "^data")],
        "vectors": [{"data": "16'hA55A", "mask": "16'h0FF0"}, {"data": "16'h1234", "mask": "16'h00FF"}, {"data": "16'hF00F", "mask": "16'hAAAA"}],
    },
    {
        "name": "case14_bitmix_mask_op",
        "module": "bitmix_unit_b",
        "inputs": [("data", "[15:0]"), ("mask", "[15:0]")],
        "outputs": [("upper_xor", "[7:0]"), ("masked_lo", "[7:0]"), ("parity", "")],
        "golden_assigns": [("upper_xor", "data[15:8] ^ mask[15:8]"), ("masked_lo", "data[7:0] & mask[7:0]"), ("parity", "^data")],
        "buggy_assigns": [("upper_xor", "data[15:8] ^ mask[15:8]"), ("masked_lo", "data[7:0] | mask[7:0]"), ("parity", "^data")],
        "vectors": [{"data": "16'h0F0F", "mask": "16'h3333"}, {"data": "16'hFFFF", "mask": "16'h00FF"}, {"data": "16'h1234", "mask": "16'h4321"}],
    },
    {
        "name": "case15_bitmix_parity",
        "module": "bitmix_unit_c",
        "inputs": [("data", "[15:0]"), ("mask", "[15:0]")],
        "outputs": [("upper_xor", "[7:0]"), ("masked_lo", "[7:0]"), ("parity", "")],
        "golden_assigns": [("upper_xor", "data[15:8] ^ mask[15:8]"), ("masked_lo", "data[7:0] & mask[7:0]"), ("parity", "^data")],
        "buggy_assigns": [("upper_xor", "data[15:8] ^ mask[15:8]"), ("masked_lo", "data[7:0] & mask[7:0]"), ("parity", "^mask")],
        "vectors": [{"data": "16'h0001", "mask": "16'h0000"}, {"data": "16'hF0F0", "mask": "16'h00FF"}, {"data": "16'hAAAA", "mask": "16'h5555"}],
    },
    {
        "name": "case16_bitmix_invert",
        "module": "bitmix_unit_d",
        "inputs": [("data", "[15:0]"), ("mask", "[15:0]")],
        "outputs": [("upper_inv", "[7:0]"), ("lower_or", "[7:0]")],
        "golden_assigns": [("upper_inv", "~data[15:8]"), ("lower_or", "data[7:0] | mask[7:0]")],
        "buggy_assigns": [("upper_inv", "data[15:8]"), ("lower_or", "data[7:0] | mask[7:0]")],
        "vectors": [{"data": "16'hABCD", "mask": "16'h0000"}, {"data": "16'h1234", "mask": "16'h00F0"}, {"data": "16'h00FF", "mask": "16'h0F0F"}],
    },
    {
        "name": "case17_shift_left",
        "module": "shift_unit_a",
        "inputs": [("data", "[7:0]"), ("sh", "[1:0]")],
        "outputs": [("left_shift", "[7:0]"), ("right_shift", "[7:0]")],
        "golden_assigns": [("left_shift", "data << sh"), ("right_shift", "data >> sh")],
        "buggy_assigns": [("left_shift", "data >> sh"), ("right_shift", "data >> sh")],
        "vectors": [{"data": "8'h01", "sh": "2'd1"}, {"data": "8'h80", "sh": "2'd2"}, {"data": "8'h3C", "sh": "2'd3"}],
    },
    {
        "name": "case18_shift_rotate",
        "module": "shift_unit_b",
        "inputs": [("data", "[7:0]")],
        "outputs": [("rotl1", "[7:0]"), ("rotr1", "[7:0]")],
        "golden_assigns": [("rotl1", "{data[6:0], data[7]}"), ("rotr1", "{data[0], data[7:1]}")],
        "buggy_assigns": [("rotl1", "{data[0], data[7:1]}"), ("rotr1", "{data[0], data[7:1]}")],
        "vectors": [{"data": "8'h81"}, {"data": "8'h3C"}, {"data": "8'hA5"}],
    },
    {
        "name": "case19_mux_three_way",
        "module": "mux3_unit_a",
        "inputs": [("a", "[7:0]"), ("b", "[7:0]"), ("c", "[7:0]"), ("sel", "[1:0]")],
        "outputs": [("out", "[7:0]")],
        "golden_assigns": [("out", "(sel == 2'd0) ? a : ((sel == 2'd1) ? b : c)")],
        "buggy_assigns": [("out", "(sel == 2'd0) ? a : ((sel == 2'd1) ? c : b)")],
        "vectors": [{"a": "8'h01", "b": "8'h10", "c": "8'hFF", "sel": "2'd0"}, {"a": "8'h01", "b": "8'h10", "c": "8'hFF", "sel": "2'd1"}, {"a": "8'h01", "b": "8'h10", "c": "8'hFF", "sel": "2'd2"}],
    },
    {
        "name": "case20_checksum_slice",
        "module": "checksum_unit_a",
        "inputs": [("data", "[15:0]")],
        "outputs": [("checksum", "[7:0]"), ("folded", "[7:0]")],
        "golden_assigns": [("checksum", "data[15:8] + data[7:0]"), ("folded", "data[15:8] ^ data[7:0]")],
        "buggy_assigns": [("checksum", "data[15:8] + data[15:8]"), ("folded", "data[15:8] ^ data[7:0]")],
        "vectors": [{"data": "16'h1234"}, {"data": "16'hABCD"}, {"data": "16'h00FF"}],
    },
]


def main() -> None:
    BENCH_ROOT.mkdir(parents=True, exist_ok=True)
    for case in CASES:
        write_case(case)
    manifest = BENCH_ROOT / "manifest.txt"
    manifest.write_text("\n".join(case["name"] for case in CASES) + "\n", encoding="utf-8")
    print(f"Generated {len(CASES)} cases in {BENCH_ROOT}")


if __name__ == "__main__":
    main()
