`timescale 1ns / 1ps

module tb_seq_detector;

    reg  clk = 1'b0;
    reg  rst;
    reg  din;
    wire detected;

    seq_detector dut (
        .clk     (clk),
        .rst     (rst),
        .din     (din),
        .detected(detected)
    );

    always #5 clk = ~clk;

    // the bit stream, sent MSB first
    localparam [31:0] PATTERN = 32'b1011_0110_1011_1011_0001_0111_0101_1000;

    reg [3:0] history = 4'b0000;   // last 4 bits seen by the FSM
    integer i, errors = 0, hits = 0;

    always @(posedge clk) begin
        if (rst) history <= 4'b0000;
        else     history <= {history[2:0], din};
    end

    always @(posedge clk) begin
        #1;
        if (!rst) begin
            if (detected !== (history == 4'b1011)) begin
                $display("ERROR at %0t: detected=%b but last bits=%b", $time, detected, history);
                errors = errors + 1;
            end
            if (detected) begin
                hits = hits + 1;
                $display("t=%0t  pattern 1011 detected", $time);
            end
        end
    end

    initial begin
        $dumpfile("tb_seq_detector.vcd");
        $dumpvars(0, tb_seq_detector);

        rst = 1'b1; din = 1'b0;
        @(negedge clk); @(negedge clk);
        rst = 1'b0;

        for (i = 31; i >= 0; i = i - 1) begin
            din = PATTERN[i];
            @(negedge clk);
        end
        din = 1'b0;
        repeat (3) @(negedge clk);

        if (errors == 0) $display("PASS: %0d detections, all correct", hits);
        else             $display("FAIL: %0d errors", errors);
        $finish;
    end

endmodule
