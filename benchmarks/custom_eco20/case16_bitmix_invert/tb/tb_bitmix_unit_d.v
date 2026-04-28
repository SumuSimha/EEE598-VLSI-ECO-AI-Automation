`timescale 1ns/1ps

module tb_bitmix_unit_d;
    integer mismatches;
    reg [15:0] data;
    reg [15:0] mask;
    wire [7:0] upper_inv;
    wire [7:0] lower_or;
    wire [7:0] expected_upper_inv;
    wire [7:0] expected_lower_or;

    assign expected_upper_inv = ~data[15:8];
    assign expected_lower_or = data[7:0] | mask[7:0];

    bitmix_unit_d uut (
        .data(data),
        .mask(mask),
        .upper_inv(upper_inv),
        .lower_or(lower_or)
    );

    initial begin
        mismatches = 0;
        data = 16'hABCD;
        mask = 16'h0000;
        #1;
        if (upper_inv !== expected_upper_inv || lower_or !== expected_lower_or) begin
            mismatches = mismatches + 1;
            $display("Case 1 mismatch", " upper_inv=%h expected=%h", " lower_or=%h expected=%h", upper_inv, expected_upper_inv, lower_or, expected_lower_or);
        end
        data = 16'h1234;
        mask = 16'h00F0;
        #1;
        if (upper_inv !== expected_upper_inv || lower_or !== expected_lower_or) begin
            mismatches = mismatches + 1;
            $display("Case 2 mismatch", " upper_inv=%h expected=%h", " lower_or=%h expected=%h", upper_inv, expected_upper_inv, lower_or, expected_lower_or);
        end
        data = 16'h00FF;
        mask = 16'h0F0F;
        #1;
        if (upper_inv !== expected_upper_inv || lower_or !== expected_lower_or) begin
            mismatches = mismatches + 1;
            $display("Case 3 mismatch", " upper_inv=%h expected=%h", " lower_or=%h expected=%h", upper_inv, expected_upper_inv, lower_or, expected_lower_or);
        end
        if (mismatches == 0)
            $display("[SUCCESS] All vectors matched");
        else
            $display("[MISMATCH] Total mismatches: %0d", mismatches);
        $finish;
    end
endmodule
