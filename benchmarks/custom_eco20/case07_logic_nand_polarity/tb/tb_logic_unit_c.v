`timescale 1ns/1ps

module tb_logic_unit_c;
    integer mismatches;
    reg [7:0] a;
    reg [7:0] b;
    wire [7:0] nand_out;
    wire [7:0] xor_out;
    wire [7:0] expected_nand_out;
    wire [7:0] expected_xor_out;

    assign expected_nand_out = ~(a & b);
    assign expected_xor_out = a ^ b;

    logic_unit_c uut (
        .a(a),
        .b(b),
        .nand_out(nand_out),
        .xor_out(xor_out)
    );

    initial begin
        mismatches = 0;
        a = 8'hFF;
        b = 8'h0F;
        #1;
        if (nand_out !== expected_nand_out || xor_out !== expected_xor_out) begin
            mismatches = mismatches + 1;
            $display("Case 1 mismatch", " nand_out=%h expected=%h", " xor_out=%h expected=%h", nand_out, expected_nand_out, xor_out, expected_xor_out);
        end
        a = 8'h81;
        b = 8'h18;
        #1;
        if (nand_out !== expected_nand_out || xor_out !== expected_xor_out) begin
            mismatches = mismatches + 1;
            $display("Case 2 mismatch", " nand_out=%h expected=%h", " xor_out=%h expected=%h", nand_out, expected_nand_out, xor_out, expected_xor_out);
        end
        a = 8'h55;
        b = 8'hAA;
        #1;
        if (nand_out !== expected_nand_out || xor_out !== expected_xor_out) begin
            mismatches = mismatches + 1;
            $display("Case 3 mismatch", " nand_out=%h expected=%h", " xor_out=%h expected=%h", nand_out, expected_nand_out, xor_out, expected_xor_out);
        end
        if (mismatches == 0)
            $display("[SUCCESS] All vectors matched");
        else
            $display("[MISMATCH] Total mismatches: %0d", mismatches);
        $finish;
    end
endmodule
