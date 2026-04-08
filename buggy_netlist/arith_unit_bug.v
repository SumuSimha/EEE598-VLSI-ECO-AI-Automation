module arith_unit (
    input [7:0] a,
    input [7:0] b,
    output [7:0] sum,
    output [7:0] xor_out
);
    // BUG 1: Using bitwise AND instead of addition for the lower nibble
    assign sum[3:0] = a[3:0] & b[3:0]; 
    assign sum[7:4] = a[7:4] + b[7:4];

    // BUG 2: Bit-slice mismatch (Mapping bits 7:4 to 3:0)
    assign xor_out[3:0] = a[7:4] ^ b[7:4]; 
    assign xor_out[7:4] = a[3:0] ^ b[3:0];

endmodule