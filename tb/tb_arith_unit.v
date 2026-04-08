`timescale 1ns/1ps

module tb_arith_unit;
    reg [7:0] a, b;
    wire [7:0] sum, xor_out;
    
    // Instantiate the Unit Under Test (UUT)
    arith_unit uut (
        .a(a), .b(b), 
        .sum(sum), .xor_out(xor_out)
    );

    initial begin
        $display("Starting Simulation...");
        
        // Test Case 1
        a = 8'h0F; b = 8'h01;
        #10;
        if (sum !== (a + b) || xor_out !== (a ^ b)) 
            $display("[MISMATCH] Expected Sum: %h, Got: %h | Expected XOR: %h, Got: %h", (a+b), sum, (a^b), xor_out);
        else
            $display("[SUCCESS] Matches Golden RTL");

        // Test Case 2
        a = 8'hAA; b = 8'h55;
        #10;
        if (sum !== (a + b) || xor_out !== (a ^ b)) 
            $display("[MISMATCH] Expected Sum: %h, Got: %h", (a+b), sum);
        else
            $display("[SUCCESS] Matches Golden RTL");

        $finish;
    end
endmodule