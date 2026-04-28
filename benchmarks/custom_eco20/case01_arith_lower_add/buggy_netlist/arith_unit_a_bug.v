module arith_unit_a (
    input [7:0] a,
    input [7:0] b,
    output [7:0] sum,
    output [7:0] xor_out
);
    assign sum[3:0] = a[3:0] & b[3:0];
    assign sum[7:4] = a[7:4] + b[7:4];
    assign xor_out = a ^ b;
endmodule
