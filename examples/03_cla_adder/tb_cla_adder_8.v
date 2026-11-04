`timescale 1ns / 1ps

// Randomised self-checking testbench: compares the CLA with a + b + cin.
module tb_cla_adder_8;

    reg  [7:0] a, b;
    reg        cin;
    wire [7:0] sum;
    wire       cout;

    cla_adder_8 dut (
        .a   (a),
        .b   (b),
        .cin (cin),
        .sum (sum),
        .cout(cout)
    );

    integer i;
    integer errors = 0;
    reg [8:0] expected;

    task check;
        begin
            #10;
            expected = a + b + cin;
            if ({cout, sum} !== expected) begin
                $display("ERROR: %0d + %0d + %0d -> %0d (expected %0d)", a, b, cin, {cout, sum}, expected);
                errors = errors + 1;
            end
        end
    endtask

    initial begin
        $dumpfile("tb_cla_adder_8.vcd");
        $dumpvars(0, tb_cla_adder_8);

        // corner cases
        a = 8'd0;   b = 8'd0;   cin = 0; check;
        a = 8'd255; b = 8'd1;   cin = 0; check;
        a = 8'd255; b = 8'd255; cin = 1; check;
        a = 8'd128; b = 8'd128; cin = 0; check;
        a = 8'h0F;  b = 8'h01;  cin = 0; check;   // carry crosses the 4-bit boundary

        // random cases
        for (i = 0; i < 200; i = i + 1) begin
            a = $random; b = $random; cin = $random;
            check;
        end

        if (errors == 0) $display("PASS: 205 additions correct");
        else             $display("FAIL: %0d errors", errors);
        $finish;
    end

endmodule
