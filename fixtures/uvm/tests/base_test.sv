`ifndef BASE_TEST_SV
`define BASE_TEST_SV

class base_test extends uvm_test;
    `uvm_component_utils(base_test)

    base_env env;

    function new(string name = "base_test", uvm_component parent = null);
        super.new(name, parent);
    endfunction

    virtual function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        env = base_env::type_id::create("env", this);
    endfunction

    virtual task run_phase(uvm_phase phase);
        phase.raise_objection(this);
        `uvm_info("BASE_TEST", "Executing base test sequence...", UVM_LOW)
        #100ns;
        phase.drop_objection(this);
    endtask

    virtual function void report_phase(uvm_phase phase);
        uvm_report_server svr = uvm_report_server::get_server();
        if (svr.get_severity_count(UVM_ERROR) == 0 && svr.get_severity_count(UVM_FATAL) == 0) begin
            `uvm_info("BASE_TEST", "--- UVM_TEST_PASSED ---", UVM_NONE)
        end else begin
            `uvm_error("BASE_TEST", "--- UVM_TEST_FAILED ---")
        end
    endfunction
endclass

`endif
