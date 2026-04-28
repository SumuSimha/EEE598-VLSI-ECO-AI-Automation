module arith_unit_c (
    input [7:0] a,
    input [7:0] b,
    output [7:0] sum,
    output [7:0] xor_out
);
    
    assign xor_out = a ^ b;
    assign sum = a + b;
endmodule
