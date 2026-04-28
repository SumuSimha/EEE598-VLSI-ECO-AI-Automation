module shift_unit_b (
    input [7:0] data,
    output [7:0] rotl1,
    output [7:0] rotr1
);
    assign rotl1 = {data[6:0], data[7]};
    assign rotr1 = {data[0], data[7:1]};
endmodule
