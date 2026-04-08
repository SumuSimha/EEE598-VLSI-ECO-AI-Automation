// Simple behavioral models for simulation
primitive udp_and (out, a, b);
    output out; input a, b;
    table
        0 0 : 0;
        0 1 : 0;
        1 0 : 0;
        1 1 : 1;
    endtable
endprimitive

module ANDGATE (output Y, input A, input B);
    assign Y = A & B;
endmodule