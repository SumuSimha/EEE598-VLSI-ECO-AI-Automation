module logic_unit_c (
    input [7:0] a,
    input [7:0] b,
    output [7:0] nand_out,
    output [7:0] xor_out
);
    assign nand_out = a & b;
    assign xor_out = a ^ b;
endmodule
