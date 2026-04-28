module logic_unit_d (
    input [7:0] a,
    input [7:0] b,
    input sel,
    output [7:0] pass_out,
    output [7:0] mix_out
);
    assign pass_out = sel ? a : b;
    assign mix_out = (a & b) | ({8{sel}} & a);
endmodule
