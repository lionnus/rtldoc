"""The rules that read the name of a port."""

from __future__ import annotations

from rtldoc.model import Module, Port
from rtldoc.naming import (
    interface_dir,
    is_background,
    is_clear,
    is_test_mode,
    name_direction,
    signal_kind,
)


def test_the_name_of_a_port_can_give_the_direction():
    assert name_direction("data_i") == "in"
    assert name_direction("data_in") == "in"
    assert name_direction("flags_o") == "out"
    assert name_direction("data_out") == "out"
    assert name_direction("tcdm") == ""
    assert name_direction("rst_ni") == "", "a reset is not an input by name"


def test_the_declaration_gives_the_direction_of_a_logic_port():
    assert Port("data_o", "in").graph_dir == "in", "the language wins"
    assert Port("bus", "inout").graph_dir == ""
    assert Port("bus_i", "inout").graph_dir == "in"


def test_an_interface_port_takes_the_direction_from_the_modport_first():
    """The compiler checked the modport; the name is a convention. On the HWPE
    streamer, `hwpe_stream_intf_stream.source data_in` is an output."""
    port = Port("data_in", "interface", is_interface=True, modport="source")
    assert interface_dir("source") == "out"
    assert port.graph_dir == "out"


def test_an_interface_port_with_no_modport_uses_the_name():
    port = Port("data_in", "interface", is_interface=True, modport="monitor")
    assert port.graph_dir == "in", "`monitor` gives no direction, `_in` does"
    assert Port("bus", "interface", is_interface=True,
                modport="slave").graph_dir == "in"


def test_an_interface_port_with_no_direction_at_all():
    port = Port("tcdm", "interface", is_interface=True, modport="")
    assert port.graph_dir == ""


def test_the_name_of_a_signal_gives_its_kind():
    assert signal_kind("ctrl_i") == "control"
    assert signal_kind("cfg_word") == "control"
    assert signal_kind("enable") == "control"
    assert signal_kind("flags_o") == "status"
    assert signal_kind("busy_o") == "status"
    assert signal_kind("evt_o") == "status"
    assert signal_kind("data_i") == "", "a data signal has no kind"
    assert signal_kind("") == ""


def test_a_part_of_a_word_gives_no_kind():
    """`len_i` contains `en`, and `moden` contains `mode`. Neither is control."""
    assert signal_kind("len_i") == ""
    assert signal_kind("modena") == ""


def test_a_rule_of_the_project_comes_before_the_common_tokens():
    conv = {"control": [r"^csr_"], "status": [r"_sts$"]}
    assert signal_kind("csr_word", conv) == "control"
    assert signal_kind("engine_sts", conv) == "status"
    assert signal_kind("ctrl_i", conv) == "control", "the common tokens still work"


def test_a_rule_that_is_not_a_regex_is_ignored():
    assert signal_kind("data_i", {"control": ["("]}) == ""
    assert signal_kind("ctrl_i", {"control": ["("]}) == "control"


def test_a_clear_and_a_test_mode_are_background_signals():
    assert is_clear("clear_i") and is_clear("clr")
    assert not is_clear("clearance"), "only the whole word is a clear"
    assert is_test_mode("test_mode_i") and is_test_mode("scan_en") and is_test_mode("dft_i")
    assert not is_test_mode("latest_i")
    assert is_background("clk_i") and is_background("rst_ni")
    assert is_background("clear_i") and is_background("test_mode_i")
    assert not is_background("data_i")


def test_a_background_signal_has_no_kind():
    """`test_mode_i` contains `mode`, but it is not a control signal: it goes
    to each instance, as a clock does, and the graphs leave it out."""
    assert signal_kind("test_mode_i") == ""
    assert signal_kind("clear_i") == ""


def test_the_module_lists_its_clears_and_test_pins():
    mod = Module(name="m", ports=[
        Port("clk_i", "in"), Port("rst_ni", "in"), Port("clear_i", "in"),
        Port("test_mode_i", "in"), Port("data_i", "in"),
    ])
    assert [p.name for p in mod.clears] == ["clear_i"]
    assert [p.name for p in mod.test_modes] == ["test_mode_i"]
