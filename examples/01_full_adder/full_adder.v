`timescale 1ns / 1ps

// Full adder built from two half adders and an OR gate.
module full_adder (
    input  wire a,
    input  wire b,
    input  wire cin,
    output wire sum,
    output wire cout
);

    wire s1, c1, c2;

    half_adder ha1 (.a(a),  .b(b),   .sum(s1),  .carry(c1));
    half_adder ha2 (.a(s1), .b(cin), .sum(sum), .carry(c2));

    assign cout = c1 | c2;

endmodule
