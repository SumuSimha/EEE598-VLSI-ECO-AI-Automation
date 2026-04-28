`timescale 1ns/1ps

module tb_shift_unit_a;
    integer mismatches;
    reg [7:0] data;
    reg [1:0] sh;
    wire [7:0] left_shift;
    wire [7:0] right_shift;
    wire [7:0] expected_left_shift;
    wire [7:0] expected_right_shift;

    assign expected_left_shift = data << sh;
    assign expected_right_shift = data >> sh;

    shift_unit_a uut (
        .data(data),
        .sh(sh),
        .left_shift(left_shift),
        .right_shift(right_shift)
    );

    initial begin
        mismatches = 0;
        data = 8'h01;
        sh = 2'd1;
        #1;
        if (left_shift !== expected_left_shift || right_shift !== expected_right_shift) begin
            mismatches = mismatches + 1;
            $display("Case 1 mismatch", " left_shift=%h expected=%h", " right_shift=%h expected=%h", left_shift, expected_left_shift, right_shift, expected_right_shift);
        end
        data = 8'h80;
        sh = 2'd2;
        #1;
        if (left_shift !== expected_left_shift || right_shift !== expected_right_shift) begin
            mismatches = mismatches + 1;
            $display("Case 2 mismatch", " left_shift=%h expected=%h", " right_shift=%h expected=%h", left_shift, expected_left_shift, right_shift, expected_right_shift);
        end
        data = 8'h3C;
        sh = 2'd3;
        #1;
        if (left_shift !== expected_left_shift || right_shift !== expected_right_shift) begin
            mismatches = mismatches + 1;
            $display("Case 3 mismatch", " left_shift=%h expected=%h", " right_shift=%h expected=%h", left_shift, expected_left_shift, right_shift, expected_right_shift);
        end
        if (mismatches == 0)
            $display("[SUCCESS] All vectors matched");
        else
            $display("[MISMATCH] Total mismatches: %0d", mismatches);
        $finish;
    end
endmodule
