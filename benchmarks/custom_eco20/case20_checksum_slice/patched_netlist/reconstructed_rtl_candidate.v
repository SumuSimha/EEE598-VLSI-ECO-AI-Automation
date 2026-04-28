module checksum_unit_a(data, checksum, folded);
    input [15:0] data;
    output [7:0] checksum;
    output [7:0] folded;

    // Reconstructed RTL intent candidate derived from the golden reference
    assign checksum = (data + data);
    assign folded = (data ^ data);
endmodule
