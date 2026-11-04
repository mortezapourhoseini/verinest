`timescale 1ns / 1ps

// Self-checking ALU testbench with a behavioural reference model.
module tb_alu;

    reg  [7:0] a, b;
    reg  [2:0] op;
    wire [7:0] y;
    wire       zero, carry, overflow, negative;

    alu dut (
        .a       (a),
        .b       (b),
        .op      (op),
        .y       (y),
        .zero    (zero),
        .carry   (carry),
        .overflow(overflow),
        .negative(negative)
    );

    // ---- reference model ----
    reg [7:0] exp_y;
    reg       exp_c, exp_v;
    reg [8:0] t;

    task model;
        begin
            exp_c = 1'b0;
            exp_v = 1'b0;
            case (op)
                3'd0: begin
                    t = a + b;  exp_y = t[7:0];  exp_c = t[8];
                    exp_v = ($signed(a) + $signed(b) > 127) || ($signed(a) + $signed(b) < -128);
                end
                3'd1: begin
                    t = a - b;  exp_y = t[7:0];  exp_c = (a < b);
                    exp_v = ($signed(a) - $signed(b) > 127) || ($signed(a) - $signed(b) < -128);
                end
                3'd2: exp_y = a & b;
                3'd3: exp_y = a | b;
                3'd4: exp_y = a ^ b;
                3'd5: exp_y = ($signed(a) < $signed(b)) ? 8'd1 : 8'd0;
                3'd6: exp_y = a << b[2:0];
                default: exp_y = a >> b[2:0];
            endcase
        end
    endtask

    integer i;
    integer errors = 0;

    task run_one;
        begin
            #10;
            model;
            if (y !== exp_y || carry !== exp_c || overflow !== exp_v ||
                zero !== (exp_y == 0) || negative !== exp_y[7]) begin
                $display("ERROR: op=%0d a=%0d b=%0d -> y=%0d c=%b v=%b | expected y=%0d c=%b v=%b",
                         op, a, b, y, carry, overflow, exp_y, exp_c, exp_v);
                errors = errors + 1;
            end
        end
    endtask

    initial begin
        $dumpfile("tb_alu.vcd");
        $dumpvars(0, tb_alu);

        // directed tests, one per operation
        op = 3'd0; a = 8'd100; b = 8'd27;  run_one; $display("ADD 100 + 27      = %0d", y);
        op = 3'd0; a = 8'd127; b = 8'd1;   run_one; $display("ADD 127 + 1       = %0d  overflow=%b", $signed(y), overflow);
        op = 3'd1; a = 8'd5;   b = 8'd9;   run_one; $display("SUB 5 - 9         = %0d  borrow=%b", $signed(y), carry);
        op = 3'd2; a = 8'hF0;  b = 8'h3C;  run_one; $display("AND F0 & 3C       = %h", y);
        op = 3'd3; a = 8'hF0;  b = 8'h0F;  run_one; $display("OR  F0 | 0F       = %h", y);
        op = 3'd4; a = 8'hAA;  b = 8'hFF;  run_one; $display("XOR AA ^ FF       = %h", y);
        op = 3'd5; a = -8'sd3; b = 8'd2;   run_one; $display("SLT -3 < 2        = %0d", y);
        op = 3'd6; a = 8'd1;   b = 8'd7;   run_one; $display("SLL 1 << 7        = %0d", y);
        op = 3'd7; a = 8'd128; b = 8'd3;   run_one; $display("SRL 128 >> 3      = %0d", y);
        op = 3'd1; a = 8'd42;  b = 8'd42;  run_one; $display("SUB 42 - 42 = %0d  zero=%b", y, zero);

        // random tests
        for (i = 0; i < 400; i = i + 1) begin
            a = $random; b = $random; op = $random;
            run_one;
        end

        if (errors == 0) $display("PASS: ALU matches the reference model");
        else             $display("FAIL: %0d errors", errors);
        $finish;
    end

endmodule
