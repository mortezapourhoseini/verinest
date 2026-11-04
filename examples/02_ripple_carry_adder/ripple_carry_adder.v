`timescale 1ns / 1ps

// N-bit ripple-carry adder: N full adders, the carry-out of each
// stage feeds the carry-in of the next one.
module ripple_carry_adder #(
    parameter N = 4
) (
    input  wire [N-1:0] a,
    input  wire [N-1:0] b,
    input  wire         cin,
    output wire [N-1:0] sum,
    output wire         cout
);

    wire [N:0] c;          // c[0] = cin, c[N] = cout
    assign c[0] = cin;

    genvar i;
    generate
        for (i = 0; i < N; i = i + 1) begin : stage
            full_adder fa (
                .a   (a[i]),
                .b   (b[i]),
                .cin (c[i]),
                .sum (sum[i]),
                .cout(c[i+1])
            );
        end
    endgenerate

    assign cout = c[N];

endmodule
