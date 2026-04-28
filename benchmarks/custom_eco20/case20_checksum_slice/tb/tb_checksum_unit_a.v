`timescale 1ns/1ps

module tb_checksum_unit_a;
    integer mismatches;
    reg [15:0] data;
    wire [7:0] checksum;
    wire [7:0] folded;
    wire [7:0] expected_checksum;
    wire [7:0] expected_folded;

    assign expected_checksum = data[15:8] + data[7:0];
    assign expected_folded = data[15:8] ^ data[7:0];

    checksum_unit_a uut (
        .data(data),
        .checksum(checksum),
        .folded(folded)
    );

    initial begin
        mismatches = 0;
        data = 16'h1234;
        #1;
        if (checksum !== expected_checksum || folded !== expected_folded) begin
            mismatches = mismatches + 1;
            $display("Case 1 mismatch", " checksum=%h expected=%h", " folded=%h expected=%h", checksum, expected_checksum, folded, expected_folded);
        end
        data = 16'hABCD;
        #1;
        if (checksum !== expected_checksum || folded !== expected_folded) begin
            mismatches = mismatches + 1;
            $display("Case 2 mismatch", " checksum=%h expected=%h", " folded=%h expected=%h", checksum, expected_checksum, folded, expected_folded);
        end
        data = 16'h00FF;
        #1;
        if (checksum !== expected_checksum || folded !== expected_folded) begin
            mismatches = mismatches + 1;
            $display("Case 3 mismatch", " checksum=%h expected=%h", " folded=%h expected=%h", checksum, expected_checksum, folded, expected_folded);
        end
        if (mismatches == 0)
            $display("[SUCCESS] All vectors matched");
        else
            $display("[MISMATCH] Total mismatches: %0d", mismatches);
        $finish;
    end
endmodule
