`timescale 1ns / 1ps

// 8 x 8-bit register file
//   - 2 read ports  (combinational / asynchronous)
//   - 1 write port  (on the rising clock edge when we = 1)
//   - register 0 always reads 0
module register_file (
    input  wire       clk,
    input  wire       we,
    input  wire [2:0] waddr,
    input  wire [7:0] wdata,
    input  wire [2:0] raddr1,
    input  wire [2:0] raddr2,
    output wire [7:0] rdata1,
    output wire [7:0] rdata2
);

    reg [7:0] regs [0:7];

    integer i;
    initial begin
        for (i = 0; i < 8; i = i + 1)
            regs[i] = 8'd0;
    end

    always @(posedge clk) begin
        if (we && waddr != 3'd0)
            regs[waddr] <= wdata;
    end

    assign rdata1 = (raddr1 == 3'd0) ? 8'd0 : regs[raddr1];
    assign rdata2 = (raddr2 == 3'd0) ? 8'd0 : regs[raddr2];

endmodule
