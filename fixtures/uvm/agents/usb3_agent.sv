`ifndef USB3_AGENT_SV
`define USB3_AGENT_SV

class usb3_agent extends uvm_agent;
    `uvm_component_utils(usb3_agent)

    function new(string name = "usb3_agent", uvm_component parent = null);
        super.new(name, parent);
    endfunction

    virtual function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        `uvm_info("USB3_AGENT", "Building USB3 Verification Agent...", UVM_LOW)
    endfunction
endclass

`endif
