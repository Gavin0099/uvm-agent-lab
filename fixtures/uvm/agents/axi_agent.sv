`ifndef AXI_AGENT_SV
`define AXI_AGENT_SV

class axi_agent extends uvm_agent;
    `uvm_component_utils(axi_agent)

    function new(string name = "axi_agent", uvm_component parent = null);
        super.new(name, parent);
    endfunction

    virtual function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        `uvm_info("AXI_AGENT", "Building AXI Verification Agent...", UVM_LOW)
    endfunction
endclass

`endif
