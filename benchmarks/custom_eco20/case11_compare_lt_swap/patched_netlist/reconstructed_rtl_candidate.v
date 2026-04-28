module compare_unit_c(a, b, gt, eq, lt);
    input [7:0] a;
    input [7:0] b;
    output [7:0] gt;
    output [7:0] eq;
    output [7:0] lt;

    // Reconstructed RTL intent candidate derived from the golden reference
    assign lt = (a < b);
endmodule
