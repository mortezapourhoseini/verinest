// Instruction set of the simple CPU
//
//   15    12 11  10 9    8 7            0
//  +--------+------+------+--------------+
//  | opcode |  rd  |  rs  |   imm (8)    |
//  +--------+------+------+--------------+
`ifndef ISA_VH
`define ISA_VH

`define OP_NOP  4'h0   // do nothing
`define OP_LDI  4'h1   // rd = imm
`define OP_ADD  4'h2   // rd = rd + rs
`define OP_SUB  4'h3   // rd = rd - rs
`define OP_AND  4'h4   // rd = rd & rs
`define OP_OR   4'h5   // rd = rd | rs
`define OP_ADDI 4'h6   // rd = rd + imm
`define OP_JMP  4'h7   // pc = imm
`define OP_BZ   4'h8   // if (rd == 0) pc = imm
`define OP_BNZ  4'h9   // if (rd != 0) pc = imm
`define OP_HALT 4'hF   // stop

`define R0 2'd0
`define R1 2'd1
`define R2 2'd2
`define R3 2'd3

`endif
