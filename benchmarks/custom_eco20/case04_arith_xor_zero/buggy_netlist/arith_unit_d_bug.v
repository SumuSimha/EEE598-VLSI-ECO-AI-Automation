module arith_unit_d (
    input [7:0] a,
    input [7:0] b,
    output [7:0] sum,
    output [7:0] xor_out
);
    assign sum = a + b;
    assign xor_out = 8'h00;
endmodule
