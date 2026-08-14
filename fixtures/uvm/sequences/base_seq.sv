`ifndef BASE_SEQ_SV
`define BASE_SEQ_SV

class base_seq_item extends uvm_sequence_item;
    `uvm_object_utils(base_seq_item)

    rand bit [31:0] data;
    rand bit [3:0]  id;
    rand int        delay;

    constraint c_delay { delay inside {[1:10]}; }

    function new(string name = "base_seq_item");
        super.new(name);
    endfunction
endclass

class base_seq extends uvm_sequence #(base_seq_item);
    `uvm_object_utils(base_seq)

    function new(string name = "base_seq");
        super.new(name);
    endfunction

    virtual task body();
        `uvm_info("BASE_SEQ", "Starting base sequence execution...", UVM_MEDIUM)
    endtask
endclass

`endif
