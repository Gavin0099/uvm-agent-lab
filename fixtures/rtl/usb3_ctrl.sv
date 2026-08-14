// Synthesizable RTL: USB3 Controller State Machine
module usb3_ctrl (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        warm_rst_n,
    input  logic [1:0]  speed_mode,
    output logic [3:0]  ltssm_state,
    output logic [7:0]  sticky_cfg_reg
);

    typedef enum logic [3:0] {
        STATE_RESET     = 4'h0,
        STATE_RX_DETECT = 4'h1,
        STATE_POLLING   = 4'h2,
        STATE_U0        = 4'h3,
        STATE_U1        = 4'h4,
        STATE_U2        = 4'h5,
        STATE_U3        = 4'h6
    } ltssm_e;

    ltssm_e current_state, next_state;
    logic [7:0] sticky_reg;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            current_state   <= STATE_RESET;
            sticky_reg      <= 8'hA5; // Default power-on sticky value
        end else if (!warm_rst_n) begin
            current_state   <= STATE_RX_DETECT; // Warm reset transitions directly to Rx.Detect
            // Sticky register is preserved
        end else begin
            current_state   <= next_state;
        end
    end

    always_comb begin
        next_state = current_state;
        case (current_state)
            STATE_RESET:     next_state = STATE_RX_DETECT;
            STATE_RX_DETECT: next_state = STATE_POLLING;
            STATE_POLLING:   next_state = STATE_U0;
            STATE_U0:        next_state = STATE_U0;
            default:         next_state = STATE_RX_DETECT;
        endcase
    end

    assign ltssm_state    = current_state;
    assign sticky_cfg_reg = sticky_reg;

endmodule
