module logic_unit_a (
    input [7:0] a,
    input [7:0] b,
    input sel,
    output [7:0] and_out,
    output [7:0] or_out,
    output [7:0] mux_out
);
    assign and_out = a & b;
    assign or_out = a | b;
    assign mux_out = sel ? a : b;
endmodule
