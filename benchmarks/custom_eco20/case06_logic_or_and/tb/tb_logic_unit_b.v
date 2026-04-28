`timescale 1ns/1ps

module tb_logic_unit_b;
    integer mismatches;
    reg [7:0] a;
    reg [7:0] b;
    reg sel;
    wire [7:0] and_out;
    wire [7:0] or_out;
    wire [7:0] mux_out;
    wire [7:0] expected_and_out;
    wire [7:0] expected_or_out;
    wire [7:0] expected_mux_out;

    assign expected_and_out = a & b;
    assign expected_or_out = a | b;
    assign expected_mux_out = sel ? a : b;

    logic_unit_b uut (
        .a(a),
        .b(b),
        .sel(sel),
        .and_out(and_out),
        .or_out(or_out),
        .mux_out(mux_out)
    );

    initial begin
        mismatches = 0;
        a = 8'h0C;
        b = 8'h03;
        sel = 1'b0;
        #1;
        if (and_out !== expected_and_out || or_out !== expected_or_out || mux_out !== expected_mux_out) begin
            mismatches = mismatches + 1;
            $display("Case 1 mismatch", " and_out=%h expected=%h", " or_out=%h expected=%h", " mux_out=%h expected=%h", and_out, expected_and_out, or_out, expected_or_out, mux_out, expected_mux_out);
        end
        a = 8'hF0;
        b = 8'h0F;
        sel = 1'b1;
        #1;
        if (and_out !== expected_and_out || or_out !== expected_or_out || mux_out !== expected_mux_out) begin
            mismatches = mismatches + 1;
            $display("Case 2 mismatch", " and_out=%h expected=%h", " or_out=%h expected=%h", " mux_out=%h expected=%h", and_out, expected_and_out, or_out, expected_or_out, mux_out, expected_mux_out);
        end
        a = 8'h33;
        b = 8'h55;
        sel = 1'b0;
        #1;
        if (and_out !== expected_and_out || or_out !== expected_or_out || mux_out !== expected_mux_out) begin
            mismatches = mismatches + 1;
            $display("Case 3 mismatch", " and_out=%h expected=%h", " or_out=%h expected=%h", " mux_out=%h expected=%h", and_out, expected_and_out, or_out, expected_or_out, mux_out, expected_mux_out);
        end
        if (mismatches == 0)
            $display("[SUCCESS] All vectors matched");
        else
            $display("[MISMATCH] Total mismatches: %0d", mismatches);
        $finish;
    end
endmodule
