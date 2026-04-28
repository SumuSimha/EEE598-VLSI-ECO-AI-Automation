module compare_unit_d (
    input [7:0] a,
    input [7:0] b,
    output gt,
    output eq,
    output lt
);
    
    assign eq = a == b;
    assign gt = a > b;
    assign lt = a < b;
endmodule
