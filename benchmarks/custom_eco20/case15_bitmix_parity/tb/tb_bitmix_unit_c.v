`timescale 1ns/1ps

module tb_bitmix_unit_c;
    integer mismatches;
    reg [15:0] data;
    reg [15:0] mask;
    wire [7:0] upper_xor;
    wire [7:0] masked_lo;
    wire parity;
    wire [7:0] expected_upper_xor;
    wire [7:0] expected_masked_lo;
    wire expected_parity;

    assign expected_upper_xor = data[15:8] ^ mask[15:8];
    assign expected_masked_lo = data[7:0] & mask[7:0];
    assign expected_parity = ^data;

    bitmix_unit_c uut (
        .data(data),
        .mask(mask),
        .upper_xor(upper_xor),
        .masked_lo(masked_lo),
        .parity(parity)
    );

    initial begin
        mismatches = 0;
        data = 16'h0001;
        mask = 16'h0000;
        #1;
        if (upper_xor !== expected_upper_xor || masked_lo !== expected_masked_lo || parity !== expected_parity) begin
            mismatches = mismatches + 1;
            $display("Case 1 mismatch", " upper_xor=%h expected=%h", " masked_lo=%h expected=%h", " parity=%h expected=%h", upper_xor, expected_upper_xor, masked_lo, expected_masked_lo, parity, expected_parity);
        end
        data = 16'hF0F0;
        mask = 16'h00FF;
        #1;
        if (upper_xor !== expected_upper_xor || masked_lo !== expected_masked_lo || parity !== expected_parity) begin
            mismatches = mismatches + 1;
            $display("Case 2 mismatch", " upper_xor=%h expected=%h", " masked_lo=%h expected=%h", " parity=%h expected=%h", upper_xor, expected_upper_xor, masked_lo, expected_masked_lo, parity, expected_parity);
        end
        data = 16'hAAAA;
        mask = 16'h5555;
        #1;
        if (upper_xor !== expected_upper_xor || masked_lo !== expected_masked_lo || parity !== expected_parity) begin
            mismatches = mismatches + 1;
            $display("Case 3 mismatch", " upper_xor=%h expected=%h", " masked_lo=%h expected=%h", " parity=%h expected=%h", upper_xor, expected_upper_xor, masked_lo, expected_masked_lo, parity, expected_parity);
        end
        if (mismatches == 0)
            $display("[SUCCESS] All vectors matched");
        else
            $display("[MISMATCH] Total mismatches: %0d", mismatches);
        $finish;
    end
endmodule
