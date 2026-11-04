`timescale 1ns / 1ps

// Synchronous up/down counter.
// Priority: rst > load > en
module counter #(
    parameter WIDTH = 4
) (
    input  wire             clk,
    input  wire             rst,     // synchronous reset to 0
    input  wire             en,      // count when 1
    input  wire             up,      // 1 = count up, 0 = count down
    input  wire             load,    // load d into the counter
    input  wire [WIDTH-1:0] d,
    output reg  [WIDTH-1:0] q,
    output wire             tc       // terminal count: all ones (up) or zero (down)
);

    always @(posedge clk) begin
        if (rst)
            q <= {WIDTH{1'b0}};
        else if (load)
            q <= d;
        else if (en) begin
            if (up)
                q <= q + 1'b1;
            else
                q <= q - 1'b1;
        end
    end

    assign tc = up ? (q == {WIDTH{1'b1}}) : (q == {WIDTH{1'b0}});

endmodule
