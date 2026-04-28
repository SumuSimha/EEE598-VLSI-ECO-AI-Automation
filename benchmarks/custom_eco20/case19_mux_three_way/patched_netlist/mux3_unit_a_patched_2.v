module mux3_unit_a (
    input [7:0] a,
    input [7:0] b,
    input [7:0] c,
    input [1:0] sel,
    output [7:0] out
);
    
    assign out = (sel == 2'd0) ? a : ((sel == 2'd1) ? b : c);
endmodule
