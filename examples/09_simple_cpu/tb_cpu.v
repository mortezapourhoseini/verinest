`timescale 1ns / 1ps

module tb_cpu;

    reg         clk = 1'b0;
    reg         rst;
    wire [7:0]  pc;
    wire [15:0] instr;
    wire        halted;

    cpu dut (
        .clk   (clk),
        .rst   (rst),
        .pc    (pc),
        .instr (instr),
        .halted(halted)
    );

    always #5 clk = ~clk;

    integer cycles = 0;

    initial begin
        $dumpfile("tb_cpu.vcd");
        $dumpvars(0, tb_cpu);

        rst = 1'b1;
        repeat (2) @(posedge clk);
        @(negedge clk) rst = 1'b0;

        $display("cycle  pc  instr   r0  r1  r2  r3");
        while (!halted && cycles < 200) begin
            $display("%5d  %2d  %h  %3d %3d %3d %3d", cycles, pc, instr,
                     dut.r0, dut.r1, dut.r2, dut.r3);
            @(negedge clk);
            cycles = cycles + 1;
        end

        if (!halted)
            $display("FAIL: CPU did not reach HALT within 200 cycles");
        else if (dut.r0 !== 8'd55)
            $display("FAIL: r0 = %0d, expected 55", dut.r0);
        else
            $display("PASS: 1 + 2 + ... + 10 = %0d in %0d cycles", dut.r0, cycles);
        $finish;
    end

endmodule
