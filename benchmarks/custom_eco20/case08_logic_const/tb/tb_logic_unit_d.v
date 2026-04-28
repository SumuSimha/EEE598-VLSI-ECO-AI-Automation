`timescale 1ns/1ps

module tb_logic_unit_d;
    integer mismatches;
    reg [7:0] a;
    reg [7:0] b;
    reg sel;
    wire [7:0] pass_out;
    wire [7:0] mix_out;
    wire [7:0] expected_pass_out;
    wire [7:0] expected_mix_out;

    assign expected_pass_out = sel ? a : b;
    assign expected_mix_out = (a & b) | ({8{sel}} & a);

    logic_unit_d uut (
        .a(a),
        .b(b),
        .sel(sel),
        .pass_out(pass_out),
        .mix_out(mix_out)
    );

    initial begin
        mismatches = 0;
        a = 8'h01;
        b = 8'h10;
        sel = 1'b0;
        #1;
        if (pass_out !== expected_pass_out || mix_out !== expected_mix_out) begin
            mismatches = mismatches + 1;
            $display("Case 1 mismatch", " pass_out=%h expected=%h", " mix_out=%h expected=%h", pass_out, expected_pass_out, mix_out, expected_mix_out);
        end
        a = 8'hC3;
        b = 8'h3C;
        sel = 1'b1;
        #1;
        if (pass_out !== expected_pass_out || mix_out !== expected_mix_out) begin
            mismatches = mismatches + 1;
            $display("Case 2 mismatch", " pass_out=%h expected=%h", " mix_out=%h expected=%h", pass_out, expected_pass_out, mix_out, expected_mix_out);
        end
        a = 8'h5A;
        b = 8'hA5;
        sel = 1'b0;
        #1;
        if (pass_out !== expected_pass_out || mix_out !== expected_mix_out) begin
            mismatches = mismatches + 1;
            $display("Case 3 mismatch", " pass_out=%h expected=%h", " mix_out=%h expected=%h", pass_out, expected_pass_out, mix_out, expected_mix_out);
        end
        if (mismatches == 0)
            $display("[SUCCESS] All vectors matched");
        else
            $display("[MISMATCH] Total mismatches: %0d", mismatches);
        $finish;
    end
endmodule
