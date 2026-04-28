module checksum_unit_a (
    input [15:0] data,
    output [7:0] checksum,
    output [7:0] folded
);
    assign checksum = data[15:8] + data[7:0];
    assign folded = data[15:8] ^ data[7:0];
endmodule
