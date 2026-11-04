`timescale 1ns / 1ps

// Exhaustive test of a 4-bit ripple-carry adder (16 x 16 x 2 = 512 cases).
module tb_ripple_carry_adder;

    localparam N = 4;

    reg  [N-1:0] a, b;
    reg          cin;
    wire [N-1:0] sum;
    wire         cout;

    ripple_carry_adder #(.N(N)) dut (
        .a   (a),
        .b   (b),
        .cin (cin),
        .sum (sum),
        .cout(cout)
    );

    integer i;
    integer errors = 0;
    reg [N:0] expected;

    initial begin
        $dumpfile("tb_ripple_carry_adder.vcd");
        $dumpvars(0, tb_ripple_carry_adder);

        for (i = 0; i < (1 << (2*N+1)); i = i + 1) begin
            {cin, a, b} = i;
            #5;
            expected = a + b + cin;
            if ({cout, sum} !== expected) begin
                $display("ERROR: %0d + %0d + %0d = %0d, expected %0d", a, b, cin, {cout, sum}, expected);
                errors = errors + 1;
            end
        end

        // a few readable examples
        a = 4'd7;  b = 4'd5;  cin = 1'b0; #10 $display("7 + 5      = %0d", {cout, sum});
        a = 4'd15; b = 4'd1;  cin = 1'b0; #10 $display("15 + 1     = %0d (carry out = %b)", {cout, sum}, cout);
        a = 4'd9;  b = 4'd6;  cin = 1'b1; #10 $display("9 + 6 + 1  = %0d", {cout, sum});

        if (errors == 0) $display("PASS: all %0d cases correct", 1 << (2*N+1));
        else             $display("FAIL: %0d errors", errors);
        $finish;
    end

endmodule
