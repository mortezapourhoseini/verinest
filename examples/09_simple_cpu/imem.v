`timescale 1ns / 1ps
`include "isa.vh"

// Instruction memory (ROM). The program computes 1 + 2 + ... + 10 into r0.
module imem (
    input  wire [7:0]  addr,
    output reg  [15:0] data
);

    always @(*) begin
        case (addr)
            //               opcode    rd   rs   imm
            8'd0: data = {`OP_LDI,  `R0, `R0, 8'd0};    // r0 = 0          (sum)
            8'd1: data = {`OP_LDI,  `R1, `R0, 8'd10};   // r1 = 10         (counter)
            8'd2: data = {`OP_ADD,  `R0, `R1, 8'd0};    // loop: r0 = r0 + r1
            8'd3: data = {`OP_ADDI, `R1, `R0, 8'hFF};   // r1 = r1 - 1     (+255 wraps to -1)
            8'd4: data = {`OP_BNZ,  `R1, `R0, 8'd2};    // if (r1 != 0) goto loop
            8'd5: data = {`OP_HALT, `R0, `R0, 8'd0};    // done: r0 = 55
            default: data = {`OP_HALT, `R0, `R0, 8'd0};
        endcase
    end

endmodule
