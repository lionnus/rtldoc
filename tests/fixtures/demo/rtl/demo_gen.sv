// Generate blocks and one undefined submodule, for the instance walk.
module demo_gen #(
  parameter int unsigned N      = 4,
  parameter bit          ENABLE = 1
) (
  input  logic       clk_i,
  input  logic       rst_ni,
  input  logic [7:0] x_i,
  output logic [7:0] y_o
);
  logic [7:0] chain [N:0];

  assign chain[0] = x_i;

  // A for-generate makes N copies of the same instance name.
  for (genvar i = 0; i < N; i++) begin : gen_stage
    demo_adder #(.W(8)) i_stage (
      .clk_i, .rst_ni, .a_i(chain[i]), .b_i(x_i), .sum_o(chain[i+1])
    );
  end

  // An if-generate holds an instance of a module that no source file declares.
  // The instance of the branch that ENABLE does not take must stay out.
  if (ENABLE) begin : gen_opt
    demo_missing_cell i_missing (.clk_i, .d_i(chain[N]), .q_o(y_o));
  end else begin : gen_opt
    demo_adder #(.W(8)) i_dead (
      .clk_i, .rst_ni, .a_i(chain[N]), .b_i(x_i), .sum_o(y_o)
    );
  end
endmodule
