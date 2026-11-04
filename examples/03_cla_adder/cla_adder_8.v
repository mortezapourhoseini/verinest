`timescale 1ns / 1ps

// 8-bit adder made of two 4-bit carry-lookahead blocks.
module cla_adder_8 (
    input  wire [7:0] a,
    input  wire [7:0] b,
    input  wire       cin,
    output wire [7:0] sum,
    output wire       cout
);

    wire c4;
    wire pg_lo, gg_lo, pg_hi, gg_hi;

    cla_4bit lo (
        .a   (a[3:0]),
        .b   (b[3:0]),
        .cin (cin),
        .sum (sum[3:0]),
        .cout(c4),
        .pg  (pg_lo),
        .gg  (gg_lo)
    );

    cla_4bit hi (
        .a   (a[7:4]),
        .b   (b[7:4]),
        .cin (c4),
        .sum (sum[7:4]),
        .cout(cout),
        .pg  (pg_hi),
        .gg  (gg_hi)
    );

endmodule
