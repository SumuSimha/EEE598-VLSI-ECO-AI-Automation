module mux3_unit_a(a, b, c, sel, out);
    input [7:0] a;
    input [7:0] b;
    input [7:0] c;
    input [1:0] sel;
    output [7:0] out;

    // Reconstructed RTL intent candidate derived from the golden reference
    assign out = ((sel == 2'd0) ? a : ((sel == 2'd1) ? b : c));
endmodule
