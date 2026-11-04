`timescale 1ns / 1ps
`include "isa.vh"

// Single-cycle 8-bit CPU: every instruction is fetched, decoded,
// executed and written back in ONE clock cycle.
module cpu (
    input  wire        clk,
    input  wire        rst,       // synchronous, active high
    output reg  [7:0]  pc,
    output wire [15:0] instr,
    output reg         halted
);

    // ---------------- fetch ----------------
    imem rom (
        .addr(pc),
        .data(instr)
    );

    // ---------------- decode ----------------
    wire [3:0] opcode = instr[15:12];
    wire [1:0] rd     = instr[11:10];
    wire [1:0] rs     = instr[9:8];
    wire [7:0] imm    = instr[7:0];

    // ---------------- register file ----------------
    reg  [7:0] regs [0:3];
    wire [7:0] rd_val = regs[rd];
    wire [7:0] rs_val = regs[rs];

    // copies of the registers so they show up in the waveform
    wire [7:0] r0 = regs[0];
    wire [7:0] r1 = regs[1];
    wire [7:0] r2 = regs[2];
    wire [7:0] r3 = regs[3];

    // ---------------- execute (combinational) ----------------
    reg [7:0] result;
    reg       write_en;
    reg [7:0] next_pc;

    always @(*) begin
        result   = 8'd0;
        write_en = 1'b0;
        next_pc  = pc + 8'd1;
        case (opcode)
            `OP_LDI:  begin result = imm;             write_en = 1'b1; end
            `OP_ADD:  begin result = rd_val + rs_val; write_en = 1'b1; end
            `OP_SUB:  begin result = rd_val - rs_val; write_en = 1'b1; end
            `OP_AND:  begin result = rd_val & rs_val; write_en = 1'b1; end
            `OP_OR:   begin result = rd_val | rs_val; write_en = 1'b1; end
            `OP_ADDI: begin result = rd_val + imm;    write_en = 1'b1; end
            `OP_JMP:  next_pc = imm;
            `OP_BZ:   if (rd_val == 8'd0) next_pc = imm;
            `OP_BNZ:  if (rd_val != 8'd0) next_pc = imm;
            `OP_HALT: next_pc = pc;
            default:  next_pc = pc + 8'd1;     // NOP
        endcase
    end

    // ---------------- state update (sequential) ----------------
    integer i;
    always @(posedge clk) begin
        if (rst) begin
            pc     <= 8'd0;
            halted <= 1'b0;
            for (i = 0; i < 4; i = i + 1)
                regs[i] <= 8'd0;
        end else if (!halted) begin
            pc <= next_pc;
            if (write_en)
                regs[rd] <= result;
            if (opcode == `OP_HALT)
                halted <= 1'b1;
        end
    end

endmodule
