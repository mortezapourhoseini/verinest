`timescale 1ns / 1ps

// Exhaustive, self-checking testbench for full_adder.
module tb_full_adder;

    reg  a, b, cin;
    wire sum, cout;

    full_adder dut (
        .a   (a),
        .b   (b),
        .cin (cin),
        .sum (sum),
        .cout(cout)
    );

    integer i;
    integer errors = 0;

    initial begin
        $dumpfile("tb_full_adder.vcd");
        $dumpvars(0, tb_full_adder);

        $display(" a b cin | cout sum");
        for (i = 0; i < 8; i = i + 1) begin
            {a, b, cin} = i[2:0];
            #10;
            $display(" %b %b  %b  |   %b   %b", a, b, cin, cout, sum);
            if ({cout, sum} !== a + b + cin) begin
                $display("ERROR: %b + %b + %b gave %b%b", a, b, cin, cout, sum);
                errors = errors + 1;
            end
        end

        if (errors == 0) $display("PASS: all 8 combinations correct");
        else             $display("FAIL: %0d errors", errors);
        $finish;
    end

endmodule
