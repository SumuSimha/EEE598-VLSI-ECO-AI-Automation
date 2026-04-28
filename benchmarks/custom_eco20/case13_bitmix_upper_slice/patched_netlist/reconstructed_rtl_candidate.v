module bitmix_unit_a(data, mask, upper_xor, masked_lo, parity);
    input [15:0] data;
    input [15:0] mask;
    output [7:0] upper_xor;
    output [7:0] masked_lo;
    output [7:0] parity;

    // Reconstructed RTL intent candidate derived from the golden reference
    assign upper_xor = (data ^ mask);
    assign masked_lo = (data & mask);
    assign parity = (Uxor data);
endmodule
