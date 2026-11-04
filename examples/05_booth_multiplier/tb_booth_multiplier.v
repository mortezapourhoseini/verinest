`timescale 1ns / 1ps

// Self-checking testbench for the Booth multiplier.
module tb_booth_multiplier;

    reg                clk = 1'b0;
    reg                rst;
    reg                start;
    reg  signed [7:0]  multiplicand, multiplier;
    wire signed [15:0] product;
    wire               busy, done;

    booth_multiplier dut (
        .clk         (clk),
        .rst         (rst),
        .start       (start),
        .multiplicand(multiplicand),
        .multiplier  (multiplier),
        .product     (product),
        .busy        (busy),
        .done        (done)
    );

    always #5 clk = ~clk;          // 100 MHz clock

    integer errors = 0;
    integer tests  = 0;
    integer i;
    reg signed [15:0] expected;

    // run one multiplication and check the result
    task multiply(input signed [7:0] x, input signed [7:0] y, input show);
        begin
            @(negedge clk);
            multiplicand = x;
            multiplier   = y;
            start        = 1'b1;
            @(negedge clk);
            start        = 1'b0;
            @(posedge done);
            #1;
            expected = x * y;
            tests = tests + 1;
            if (product !== expected) begin
                $display("ERROR: %0d * %0d = %0d, expected %0d", x, y, product, expected);
                errors = errors + 1;
            end else if (show) begin
                $display("%5d * %5d = %7d", x, y, product);
            end
        end
    endtask

    initial begin
        $dumpfile("tb_booth_multiplier.vcd");
        $dumpvars(0, tb_booth_multiplier);

        rst = 1'b1; start = 1'b0; multiplicand = 0; multiplier = 0;
        repeat (3) @(posedge clk);
        rst = 1'b0;

        multiply(8'sd7,    8'sd6,    1'b1);
        multiply(-8'sd7,   8'sd6,    1'b1);
        multiply(8'sd13,  -8'sd11,   1'b1);
        multiply(-8'sd128, -8'sd128, 1'b1);   // corner case: most negative value
        multiply(-8'sd128, 8'sd127,  1'b1);
        multiply(8'sd0,    8'sd99,   1'b1);
        multiply(-8'sd1,   -8'sd1,   1'b1);

        for (i = 0; i < 100; i = i + 1)
            multiply($random, $random, 1'b0);

        if (errors == 0) $display("PASS: %0d multiplications correct", tests);
        else             $display("FAIL: %0d of %0d multiplications wrong", errors, tests);
        $finish;
    end

endmodule
