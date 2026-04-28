module shift_unit_a (
    input [7:0] data,
    input [1:0] sh,
    output [7:0] left_shift,
    output [7:0] right_shift
);
    assign left_shift = data >> sh;
    assign right_shift = data >> sh;
endmodule
