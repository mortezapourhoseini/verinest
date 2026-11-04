`timescale 1ns / 1ps

// Radix-2 Booth multiplier (signed 8 x 8 -> 16 bit), one bit per clock.
//
// Registers:  A (accumulator), Q (multiplier), q_1 (bit right of Q[0]), M (multiplicand)
// Each step looks at {Q[0], q_1}:
//     01 -> A = A + M
//     10 -> A = A - M
//     00 / 11 -> nothing
// then {A, Q, q_1} is shifted right arithmetically by one bit.
// After 8 steps the product is {A[7:0], Q}.
module booth_multiplier (
    input  wire               clk,
    input  wire               rst,           // synchronous, active high
    input  wire               start,         // pulse to begin
    input  wire signed [7:0]  multiplicand,
    input  wire signed [7:0]  multiplier,
    output reg signed  [15:0] product,
    output reg                busy,
    output reg                done           // 1-cycle pulse when product is valid
);

    reg [8:0] A;        // one extra bit so that -(-128) still fits
    reg [7:0] Q;
    reg       q_1;
    reg [8:0] M;
    reg [3:0] count;

    // add / subtract step (combinational)
    reg [8:0] sum;
    always @(*) begin
        case ({Q[0], q_1})
            2'b01:   sum = A + M;
            2'b10:   sum = A - M;
            default: sum = A;
        endcase
    end

    always @(posedge clk) begin
        if (rst) begin
            A       <= 9'd0;
            Q       <= 8'd0;
            q_1     <= 1'b0;
            M       <= 9'd0;
            count   <= 4'd0;
            busy    <= 1'b0;
            done    <= 1'b0;
            product <= 16'sd0;
        end else begin
            done <= 1'b0;
            if (start && !busy) begin
                A     <= 9'd0;
                Q     <= multiplier;
                q_1   <= 1'b0;
                M     <= {multiplicand[7], multiplicand};   // sign-extend to 9 bits
                count <= 4'd8;
                busy  <= 1'b1;
            end else if (busy) begin
                // arithmetic shift right of {sum, Q, q_1}
                {A, Q, q_1} <= {sum[8], sum, Q};
                count       <= count - 4'd1;
                if (count == 4'd1) begin
                    busy    <= 1'b0;
                    done    <= 1'b1;
                    product <= {sum, Q[7:1]};   // = {A[7:0], Q} after the last shift
                end
            end
        end
    end

endmodule
