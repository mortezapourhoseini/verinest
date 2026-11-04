`timescale 1ns / 1ps

module tb_counter;

    localparam WIDTH = 4;

    reg              clk = 1'b0;
    reg              rst, en, up, load;
    reg  [WIDTH-1:0] d;
    wire [WIDTH-1:0] q;
    wire             tc;

    counter #(.WIDTH(WIDTH)) dut (
        .clk (clk),
        .rst (rst),
        .en  (en),
        .up  (up),
        .load(load),
        .d   (d),
        .q   (q),
        .tc  (tc)
    );

    always #5 clk = ~clk;

    reg [WIDTH-1:0] model;   // expected counter value
    integer errors = 0;
    integer cycle;

    // compare after every rising edge
    always @(posedge clk) begin
        #1;
        if (q !== model) begin
            $display("ERROR at %0t: q=%0d expected %0d", $time, q, model);
            errors = errors + 1;
        end
    end

    // reference model, updated on the same edge
    always @(posedge clk) begin
        if (rst)       model <= 0;
        else if (load) model <= d;
        else if (en)   model <= up ? model + 1'b1 : model - 1'b1;
    end

    initial begin
        $dumpfile("tb_counter.vcd");
        $dumpvars(0, tb_counter);

        rst = 1; en = 0; up = 1; load = 0; d = 0; model = 0;
        @(negedge clk); @(negedge clk);
        rst = 0;

        // count up 20 times (wraps around after 15)
        en = 1; up = 1;
        for (cycle = 0; cycle < 20; cycle = cycle + 1) @(negedge clk);

        // hold
        en = 0;
        repeat (3) @(negedge clk);

        // load 9 and count down
        load = 1; d = 4'd9; @(negedge clk); load = 0;
        en = 1; up = 0;
        repeat (12) @(negedge clk);

        // reset in the middle
        rst = 1; @(negedge clk); rst = 0;
        repeat (3) @(negedge clk);

        if (errors == 0) $display("PASS: counter follows the reference model");
        else             $display("FAIL: %0d errors", errors);
        $finish;
    end

endmodule
