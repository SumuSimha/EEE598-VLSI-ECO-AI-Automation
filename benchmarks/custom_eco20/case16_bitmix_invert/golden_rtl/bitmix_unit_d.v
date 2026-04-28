module bitmix_unit_d (
    input [15:0] data,
    input [15:0] mask,
    output [7:0] upper_inv,
    output [7:0] lower_or
);
    assign upper_inv = ~data[15:8];
    assign lower_or = data[7:0] | mask[7:0];
endmodule
