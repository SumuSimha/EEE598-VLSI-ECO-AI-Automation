module bitmix_unit_b (
    input [15:0] data,
    input [15:0] mask,
    output [7:0] upper_xor,
    output [7:0] masked_lo,
    output parity
);
    assign upper_xor = data[15:8] ^ mask[15:8];
    assign masked_lo = data[7:0] | mask[7:0];
    assign parity = ^data;
endmodule
