`timescale 1ns/1ps

module tb_shift_unit_b;
    integer mismatches;
    reg [7:0] data;
    wire [7:0] rotl1;
    wire [7:0] rotr1;
    wire [7:0] expected_rotl1;
    wire [7:0] expected_rotr1;

    assign expected_rotl1 = {data[6:0], data[7]};
    assign expected_rotr1 = {data[0], data[7:1]};

    shift_unit_b uut (
        .data(data),
        .rotl1(rotl1),
        .rotr1(rotr1)
    );

    initial begin
        mismatches = 0;
        data = 8'h81;
        #1;
        if (rotl1 !== expected_rotl1 || rotr1 !== expected_rotr1) begin
            mismatches = mismatches + 1;
            $display("Case 1 mismatch", " rotl1=%h expected=%h", " rotr1=%h expected=%h", rotl1, expected_rotl1, rotr1, expected_rotr1);
        end
        data = 8'h3C;
        #1;
        if (rotl1 !== expected_rotl1 || rotr1 !== expected_rotr1) begin
            mismatches = mismatches + 1;
            $display("Case 2 mismatch", " rotl1=%h expected=%h", " rotr1=%h expected=%h", rotl1, expected_rotl1, rotr1, expected_rotr1);
        end
        data = 8'hA5;
        #1;
        if (rotl1 !== expected_rotl1 || rotr1 !== expected_rotr1) begin
            mismatches = mismatches + 1;
            $display("Case 3 mismatch", " rotl1=%h expected=%h", " rotr1=%h expected=%h", rotl1, expected_rotl1, rotr1, expected_rotr1);
        end
        if (mismatches == 0)
            $display("[SUCCESS] All vectors matched");
        else
            $display("[MISMATCH] Total mismatches: %0d", mismatches);
        $finish;
    end
endmodule
