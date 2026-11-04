`timescale 1ns / 1ps

// 4-bit carry-lookahead adder.
//   g[i] = a[i] & b[i]   (this bit GENERATES a carry)
//   p[i] = a[i] ^ b[i]   (this bit PROPAGATES an incoming carry)
// All carries are computed in parallel instead of rippling.
module cla_4bit (
    input  wire [3:0] a,
    input  wire [3:0] b,
    input  wire       cin,
    output wire [3:0] sum,
    output wire       cout,
    output wire       pg,     // group propagate
    output wire       gg      // group generate
);

    wire [3:0] g = a & b;
    wire [3:0] p = a ^ b;
    wire [4:0] c;

    assign c[0] = cin;
    assign c[1] = g[0] | (p[0] & c[0]);
    assign c[2] = g[1] | (p[1] & g[0]) | (p[1] & p[0] & c[0]);
    assign c[3] = g[2] | (p[2] & g[1]) | (p[2] & p[1] & g[0]) | (p[2] & p[1] & p[0] & c[0]);
    assign c[4] = g[3] | (p[3] & g[2]) | (p[3] & p[2] & g[1]) | (p[3] & p[2] & p[1] & g[0])
                | (p[3] & p[2] & p[1] & p[0] & c[0]);

    assign sum  = p ^ c[3:0];
    assign cout = c[4];
    assign pg   = &p;
    assign gg   = g[3] | (p[3] & g[2]) | (p[3] & p[2] & g[1]) | (p[3] & p[2] & p[1] & g[0]);

endmodule
