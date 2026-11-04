`timescale 1ns / 1ps

module tb_register_file;

    reg        clk = 1'b0;
    reg        we;
    reg  [2:0] waddr, raddr1, raddr2;
    reg  [7:0] wdata;
    wire [7:0] rdata1, rdata2;

    register_file dut (
        .clk   (clk),
        .we    (we),
        .waddr (waddr),
        .wdata (wdata),
        .raddr1(raddr1),
        .raddr2(raddr2),
        .rdata1(rdata1),
        .rdata2(rdata2)
    );

    always #5 clk = ~clk;

    reg [7:0] golden [0:7];   // what the registers should contain
    integer i, errors = 0;

    task write_reg(input [2:0] addr, input [7:0] data);
        begin
            @(negedge clk);
            we = 1'b1; waddr = addr; wdata = data;
            @(negedge clk);
            we = 1'b0;
            if (addr != 0) golden[addr] = data;
        end
    endtask

    initial begin
        $dumpfile("tb_register_file.vcd");
        $dumpvars(0, tb_register_file);

        we = 0; waddr = 0; wdata = 0; raddr1 = 0; raddr2 = 0;
        for (i = 0; i < 8; i = i + 1) golden[i] = 8'd0;

        // write a value into every register (including r0, which must ignore it)
        for (i = 0; i < 8; i = i + 1)
            write_reg(i, 8'h10 * i + 8'h05);

        // read every pair of registers
        for (i = 0; i < 64; i = i + 1) begin
            raddr1 = i[5:3];
            raddr2 = i[2:0];
            #2;
            if (rdata1 !== golden[raddr1] || rdata2 !== golden[raddr2]) begin
                $display("ERROR: r%0d=%h r%0d=%h (expected %h %h)", raddr1, rdata1, raddr2, rdata2,
                         golden[raddr1], golden[raddr2]);
                errors = errors + 1;
            end
        end
        $display("r0=%h r1=%h r2=%h r7=%h", golden[0], golden[1], golden[2], golden[7]);

        // write while reading the same register: new value appears after the clock edge
        raddr1 = 3'd3;
        write_reg(3'd3, 8'hAB);
        #1;
        if (rdata1 !== 8'hAB) begin
            $display("ERROR: r3 should be AB after the write, got %h", rdata1);
            errors = errors + 1;
        end

        if (errors == 0) $display("PASS: register file works");
        else             $display("FAIL: %0d errors", errors);
        $finish;
    end

endmodule
