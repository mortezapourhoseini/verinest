`timescale 1ns / 1ps

// 8-bit ALU
//   op | operation
//  ----+---------------------------------
//   0  | ADD  y = a + b
//   1  | SUB  y = a - b
//   2  | AND  y = a & b
//   3  | OR   y = a | b
//   4  | XOR  y = a ^ b
//   5  | SLT  y = (a < b) ? 1 : 0   (signed compare)
//   6  | SLL  y = a << b[2:0]
//   7  | SRL  y = a >> b[2:0]
module alu (
    input  wire [7:0] a,
    input  wire [7:0] b,
    input  wire [2:0] op,
    output reg  [7:0] y,
    output wire       zero,      // y == 0
    output reg        carry,     // ADD: carry out, SUB: borrow
    output reg        overflow,  // signed overflow (ADD / SUB)
    output wire       negative   // y[7]
);

    localparam OP_ADD = 3'd0,
               OP_SUB = 3'd1,
               OP_AND = 3'd2,
               OP_OR  = 3'd3,
               OP_XOR = 3'd4,
               OP_SLT = 3'd5,
               OP_SLL = 3'd6,
               OP_SRL = 3'd7;

    reg [8:0] wide;   // 9-bit result keeps the carry

    always @(*) begin
        // default values: every output is assigned on every path (no latches)
        y        = 8'd0;
        carry    = 1'b0;
        overflow = 1'b0;
        wide     = 9'd0;
        case (op)
            OP_ADD: begin
                wide     = {1'b0, a} + {1'b0, b};
                y        = wide[7:0];
                carry    = wide[8];
                overflow = (a[7] == b[7]) && (y[7] != a[7]);
            end
            OP_SUB: begin
                wide     = {1'b0, a} - {1'b0, b};
                y        = wide[7:0];
                carry    = wide[8];                   // 1 = borrow (a < b, unsigned)
                overflow = (a[7] != b[7]) && (y[7] != a[7]);
            end
            OP_AND: y = a & b;
            OP_OR:  y = a | b;
            OP_XOR: y = a ^ b;
            OP_SLT: y = ($signed(a) < $signed(b)) ? 8'd1 : 8'd0;
            OP_SLL: y = a << b[2:0];
            OP_SRL: y = a >> b[2:0];
            default: y = 8'd0;
        endcase
    end

    assign zero     = (y == 8'd0);
    assign negative = y[7];

endmodule
