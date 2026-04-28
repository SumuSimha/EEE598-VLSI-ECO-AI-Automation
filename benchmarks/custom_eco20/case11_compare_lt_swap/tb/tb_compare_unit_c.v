`timescale 1ns/1ps

module tb_compare_unit_c;
    integer mismatches;
    reg [7:0] a;
    reg [7:0] b;
    wire gt;
    wire eq;
    wire lt;
    wire expected_gt;
    wire expected_eq;
    wire expected_lt;

    assign expected_gt = a > b;
    assign expected_eq = a == b;
    assign expected_lt = a < b;

    compare_unit_c uut (
        .a(a),
        .b(b),
        .gt(gt),
        .eq(eq),
        .lt(lt)
    );

    initial begin
        mismatches = 0;
        a = 8'h0A;
        b = 8'h0B;
        #1;
        if (gt !== expected_gt || eq !== expected_eq || lt !== expected_lt) begin
            mismatches = mismatches + 1;
            $display("Case 1 mismatch", " gt=%h expected=%h", " eq=%h expected=%h", " lt=%h expected=%h", gt, expected_gt, eq, expected_eq, lt, expected_lt);
        end
        a = 8'h10;
        b = 8'h03;
        #1;
        if (gt !== expected_gt || eq !== expected_eq || lt !== expected_lt) begin
            mismatches = mismatches + 1;
            $display("Case 2 mismatch", " gt=%h expected=%h", " eq=%h expected=%h", " lt=%h expected=%h", gt, expected_gt, eq, expected_eq, lt, expected_lt);
        end
        a = 8'h04;
        b = 8'h04;
        #1;
        if (gt !== expected_gt || eq !== expected_eq || lt !== expected_lt) begin
            mismatches = mismatches + 1;
            $display("Case 3 mismatch", " gt=%h expected=%h", " eq=%h expected=%h", " lt=%h expected=%h", gt, expected_gt, eq, expected_eq, lt, expected_lt);
        end
        if (mismatches == 0)
            $display("[SUCCESS] All vectors matched");
        else
            $display("[MISMATCH] Total mismatches: %0d", mismatches);
        $finish;
    end
endmodule
