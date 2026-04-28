`timescale 1ns/1ps

module tb_arith_unit_a;
    integer mismatches;
    reg [7:0] a;
    reg [7:0] b;
    wire [7:0] sum;
    wire [7:0] xor_out;
    wire [7:0] expected_sum;
    wire [7:0] expected_xor_out;

    assign expected_sum = a + b;
    assign expected_xor_out = a ^ b;

    arith_unit_a uut (
        .a(a),
        .b(b),
        .sum(sum),
        .xor_out(xor_out)
    );

    initial begin
        mismatches = 0;
        a = 8'h0F;
        b = 8'h01;
        #1;
        if (sum !== expected_sum || xor_out !== expected_xor_out) begin
            mismatches = mismatches + 1;
            $display("Case 1 mismatch", " sum=%h expected=%h", " xor_out=%h expected=%h", sum, expected_sum, xor_out, expected_xor_out);
        end
        a = 8'hA5;
        b = 8'h3C;
        #1;
        if (sum !== expected_sum || xor_out !== expected_xor_out) begin
            mismatches = mismatches + 1;
            $display("Case 2 mismatch", " sum=%h expected=%h", " xor_out=%h expected=%h", sum, expected_sum, xor_out, expected_xor_out);
        end
        a = 8'h80;
        b = 8'h11;
        #1;
        if (sum !== expected_sum || xor_out !== expected_xor_out) begin
            mismatches = mismatches + 1;
            $display("Case 3 mismatch", " sum=%h expected=%h", " xor_out=%h expected=%h", sum, expected_sum, xor_out, expected_xor_out);
        end
        if (mismatches == 0)
            $display("[SUCCESS] All vectors matched");
        else
            $display("[MISMATCH] Total mismatches: %0d", mismatches);
        $finish;
    end
endmodule
