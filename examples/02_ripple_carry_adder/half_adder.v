`timescale 1ns / 1ps

// Half adder: adds two 1-bit numbers.
//   sum   = a XOR b
//   carry = a AND b
module half_adder (
    input  wire a,
    input  wire b,
    output wire sum,
    output wire carry
);

    assign sum   = a ^ b;
    assign carry = a & b;

endmodule
