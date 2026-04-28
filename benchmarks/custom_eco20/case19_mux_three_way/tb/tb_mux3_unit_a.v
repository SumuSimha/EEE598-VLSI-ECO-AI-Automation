`timescale 1ns/1ps

module tb_mux3_unit_a;
    integer mismatches;
    reg [7:0] a;
    reg [7:0] b;
    reg [7:0] c;
    reg [1:0] sel;
    wire [7:0] out;
    wire [7:0] expected_out;

    assign expected_out = (sel == 2'd0) ? a : ((sel == 2'd1) ? b : c);

    mux3_unit_a uut (
        .a(a),
        .b(b),
        .c(c),
        .sel(sel),
        .out(out)
    );

    initial begin
        mismatches = 0;
        a = 8'h01;
        b = 8'h10;
        c = 8'hFF;
        sel = 2'd0;
        #1;
        if (out !== expected_out) begin
            mismatches = mismatches + 1;
            $display("Case 1 mismatch", " out=%h expected=%h", out, expected_out);
        end
        a = 8'h01;
        b = 8'h10;
        c = 8'hFF;
        sel = 2'd1;
        #1;
        if (out !== expected_out) begin
            mismatches = mismatches + 1;
            $display("Case 2 mismatch", " out=%h expected=%h", out, expected_out);
        end
        a = 8'h01;
        b = 8'h10;
        c = 8'hFF;
        sel = 2'd2;
        #1;
        if (out !== expected_out) begin
            mismatches = mismatches + 1;
            $display("Case 3 mismatch", " out=%h expected=%h", out, expected_out);
        end
        if (mismatches == 0)
            $display("[SUCCESS] All vectors matched");
        else
            $display("[MISMATCH] Total mismatches: %0d", mismatches);
        $finish;
    end
endmodule
