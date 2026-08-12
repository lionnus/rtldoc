"""The rules that read the name of a port."""

from __future__ import annotations

from rtldoc.model import Port
from rtldoc.naming import interface_dir, name_direction, signal_kind


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


def test_an_interface_port_takes_the_direction_from_the_name_first():
    port = Port("data_in", "interface", is_interface=True, modport="source")
    assert interface_dir("source") == "out", "the modport says the other way"
    assert port.graph_dir == "in"


def test_an_interface_port_with_no_name_ending_uses_the_modport():
    port = Port("bus", "interface", is_interface=True, modport="slave")
    assert port.graph_dir == "in"


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
