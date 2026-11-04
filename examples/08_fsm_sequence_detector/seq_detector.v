`timescale 1ns / 1ps

// Moore FSM that raises `detected` for one cycle after the input
// stream contains 1011. Overlapping patterns are detected:
//   din:      1 0 1 1 0 1 1
//   detected:         1     1
module seq_detector (
    input  wire clk,
    input  wire rst,        // synchronous, active high
    input  wire din,
    output wire detected
);

    // state encoding
    localparam S_IDLE = 3'd0,   // nothing matched yet
               S_1    = 3'd1,   // seen "1"
               S_10   = 3'd2,   // seen "10"
               S_101  = 3'd3,   // seen "101"
               S_1011 = 3'd4;   // seen "1011"  -> output 1

    reg [2:0] state, next_state;

    // 1) state register (sequential)
    always @(posedge clk) begin
        if (rst)
            state <= S_IDLE;
        else
            state <= next_state;
    end

    // 2) next-state logic (combinational)
    always @(*) begin
        next_state = state;
        case (state)
            S_IDLE: next_state = din ? S_1    : S_IDLE;
            S_1:    next_state = din ? S_1    : S_10;
            S_10:   next_state = din ? S_101  : S_IDLE;
            S_101:  next_state = din ? S_1011 : S_10;
            S_1011: next_state = din ? S_1    : S_10;
            default: next_state = S_IDLE;
        endcase
    end

    // 3) output logic (Moore: depends on the state only)
    assign detected = (state == S_1011);

endmodule
