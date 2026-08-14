// Synthesizable RTL: AXI Stream FIFO
module axi_fifo #(
    parameter DATA_WIDTH = 32,
    parameter DEPTH      = 16
)(
    input  logic                  clk,
    input  logic                  rst_n,
    // AXI Stream Slave
    input  logic [DATA_WIDTH-1:0] s_axis_tdata,
    input  logic                  s_axis_tvalid,
    output logic                  s_axis_tready,
    // AXI Stream Master
    output logic [DATA_WIDTH-1:0] m_axis_tdata,
    output logic                  m_axis_tvalid,
    input  logic                  m_axis_tready
);

    logic [DATA_WIDTH-1:0] mem [DEPTH-1:0];
    logic [$clog2(DEPTH):0] wr_ptr, rd_ptr;
    logic [$clog2(DEPTH):0] count;

    assign s_axis_tready = (count < DEPTH);
    assign m_axis_tvalid = (count > 0);
    assign m_axis_tdata  = mem[rd_ptr[$clog2(DEPTH)-1:0]];

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_ptr <= '0;
            rd_ptr <= '0;
            count  <= '0;
        end else begin
            case ({s_axis_tvalid && s_axis_tready, m_axis_tvalid && m_axis_tready})
                2'b10: begin
                    mem[wr_ptr[$clog2(DEPTH)-1:0]] <= s_axis_tdata;
                    wr_ptr <= wr_ptr + 1;
                    count  <= count + 1;
                end
                2'b01: begin
                    rd_ptr <= rd_ptr + 1;
                    count  <= count - 1;
                end
                2'b11: begin
                    mem[wr_ptr[$clog2(DEPTH)-1:0]] <= s_axis_tdata;
                    wr_ptr <= wr_ptr + 1;
                    rd_ptr <= rd_ptr + 1;
                end
                default: ;
            endcase
        end
    end

endmodule
