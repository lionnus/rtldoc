"""The inside of one module: the netlist view and the symbol view."""

from __future__ import annotations

import pytest

from rtldoc import schematic
from rtldoc.dot import C_CTRL, C_IFACE, C_IN, C_STATUS
from rtldoc.model import Design, Instance, Module, Port, PortConn


def test_internal_graph_shows_instances_and_the_net_between_them(design):
    dot = schematic.internal_dot(design, "top")
    assert "i__i_a" in dot and "i__i_b" in dot
    assert "mid" in dot, "the net joining the two instances must appear"
    assert "p__x_i" in dot and "p__y_o" in dot, "boundary ports become pins"


def test_internal_graph_omits_clocks_and_resets(design):
    """A clock net touches each instance. It hides the data flow."""
    dot = schematic.internal_dot(design, "top")
    assert "clk_i" not in dot
    assert "rst_ni" not in dot


def test_internal_graph_is_empty_for_a_leaf_module(design):
    assert schematic.internal_dot(design, "adder") == ""


def test_internal_graph_drops_single_endpoint_data_nets(design):
    """A data net with one end is not a connection. The graph does not show it."""
    design.modules["top"].instances[0].conns.append(PortConn("b_i", "dangling"))
    assert "dangling" not in schematic.internal_dot(design, "top")


def test_net_base_strips_selects_and_concatenations():
    assert schematic._net_base("data[7:0]") == "data"
    assert schematic._net_base("bus.payload") == "bus"
    assert schematic._net_base("1'b0") == ""
    assert schematic._net_base("") == ""


# -- connection roles --------------------------------------------------------


def test_connection_role_follows_the_child_port_direction(design):
    child = design.modules["adder"]
    assert schematic._role(child, "a_i") == "load"
    assert schematic._role(child, "sum_o") == "driver"
    assert schematic._role(child, "unknown_port") == "both"
    assert schematic._role(None, "a_i") == "both", "a black box has no known directions"


def test_connection_role_follows_the_modport_for_interfaces():
    assert schematic._iface_role("source") == "driver"
    assert schematic._iface_role("SINK") == "load"
    assert schematic._iface_role("monitor") == "both"
    assert schematic._iface_role("") == "both"


def test_interface_connections_use_the_modport_not_the_port_direction(design):
    conn = PortConn("bus", "i_stream", is_interface=True, modport="source")
    assert schematic._conn_role(conn, design.modules["adder"]) == "driver"


def test_a_net_with_three_endpoints_uses_a_hub(design):
    """Two ends connect directly. More ends need a signal node between them."""
    design.modules["top"].instances.append(
        Instance(name="i_c", module="adder", conns=[PortConn("a_i", "mid")])
    )
    dot = schematic.internal_dot(design, "top")
    assert '"n__mid"' in dot, "the shared net becomes its own node"


def test_a_black_box_connection_has_no_direction(design):
    """The ports of a black box are unknown. Thus the edge has no arrow."""
    design.modules["top"].instances.append(
        Instance(name="i_x", module="unknown_cell", conns=[PortConn("p", "mid")])
    )
    assert "dir=none" in schematic.internal_dot(design, "top")


def test_a_link_needs_a_unit_that_the_tool_found(design):
    assert schematic._link(design, "") == ""
    assert schematic._link(design, "not_extracted") == ""


# -- interfaces in the internal graph ----------------------------------------


@pytest.fixture
def with_interface(design) -> Design:
    """`top` gets three interface ports and an interface that it declares.

    `bus` has a modport, `data_in` has a name that gives the direction, and
    `tcdm` gives neither.
    """
    d = design
    d.modules["demo_if"] = Module(name="demo_if", kind="interface", package="demo_ip")
    for name, modport in (("bus", "master"), ("data_in", "sink"), ("tcdm", "")):
        d.modules["top"].ports.append(
            Port(name, "interface", is_interface=True, interface="demo_if",
                 modport=modport)
        )
    d.modules["top"].instances.append(
        Instance(name="stream", module="demo_if", is_interface=True)
    )
    for i, inst in enumerate(d.modules["top"].instances[:2]):
        inst.conns += [PortConn("bus_i", "bus"), PortConn("d_i", "data_in"),
                       PortConn("t_io", "tcdm"),
                       PortConn("s_o" if i == 0 else "s_i", "stream")]
    return d


def test_an_interface_port_with_no_direction_is_a_bidirectional_pin(with_interface):
    dot = schematic.internal_dot(with_interface, "top")
    assert '"p__tcdm" [shape=hexagon' in dot, "no modport and no name ending"
    assert '"p__x_i" [shape=cds' in dot, "`input` gives the direction"


def test_the_modport_of_an_interface_port_gives_the_direction(with_interface):
    """`data_in` has the `sink` modport: the data comes in. When the modport
    and the name disagree, the modport wins, because the compiler checked it."""
    dot = schematic.internal_dot(with_interface, "top")
    assert "rank=min; \"p__data_in\" [shape=cds, " in dot
    assert "orientation=180" not in dot.split('"p__data_in"')[0].split("rank=min")[-1]


def test_the_modport_gives_the_direction_when_the_name_does_not(with_interface):
    dot = schematic.internal_dot(with_interface, "top")
    assert 'rank=max; "p__bus" [shape=cds, height=0.37, margin="0.16,0.0", orientation=180' in dot


def test_each_interface_port_keeps_the_colour_of_an_interface(with_interface):
    dot = schematic.internal_dot(with_interface, "top")
    for pin in ("p__bus", "p__data_in", "p__tcdm"):
        attrs = dot.split(f'"{pin}" [')[1].split("]")[0]
        assert C_IFACE in attrs, f"{pin} must have the interface colour"
    logic = dot.split('"p__x_i" [')[1].split("]")[0]
    assert C_IN in logic and C_IFACE not in logic


def test_each_pin_and_signal_has_the_same_height(with_interface):
    dot = schematic.internal_dot(with_interface, "top")
    assert "shape=cds, height=0.37" in dot
    assert "shape=hexagon, height=0.25" in dot
    assert "shape=box, height=0.25" in dot


def test_an_interface_port_opens_its_declaration(with_interface):
    assert 'href="module-demo_if.html"' in schematic.internal_dot(with_interface, "top")


def test_a_signal_that_carries_an_interface_opens_its_declaration(with_interface):
    dot = schematic.internal_dot(with_interface, "top")
    assert '"n__stream" [shape=box, height=0.25, margin="0.10,0.0", href="module-demo_if.html"' in dot
    assert C_IFACE in dot, "the interface has its own colour"


def test_a_signal_that_is_not_an_interface_has_no_link(with_interface):
    dot = schematic.internal_dot(with_interface, "top")
    assert '"n__mid" [shape=box, height=0.25, margin="0.10,0.0", label=' in dot


def test_a_stream_shows_its_direction_and_its_sides(design):
    """The modports label the edges: the data goes from the source to the sink."""
    d = design
    d.modules["demo_if"] = Module(name="demo_if", kind="interface", package="demo_ip")
    top = d.modules["top"]
    top.instances.append(Instance(name="stream", module="demo_if", is_interface=True))
    a, b = top.instances[:2]
    a.conns.append(PortConn("push", "stream", is_interface=True, modport="source"))
    b.conns.append(PortConn("pop", "stream", is_interface=True, modport="sink"))
    dot = schematic.internal_dot(d, "top")
    assert f'"i__i_a" -> "n__stream" [label="source", color="{C_IFACE}", penwidth=1.6];' in dot
    assert f'"n__stream" -> "i__i_b" [label="sink", color="{C_IFACE}", penwidth=1.6];' in dot


# -- the control plane and the data path -------------------------------------


@pytest.fixture
def with_control(design) -> Design:
    """`top` gets a control input, a flag output and a status net inside."""
    top = design.modules["top"]
    top.ports += [Port("ctrl_i", "in"), Port("flags_o", "out")]
    a, b = top.instances
    a.conns += [PortConn("ctrl_i", "ctrl_i"), PortConn("busy_o", "flags_o"),
                PortConn("d_i", "done")]
    b.conns += [PortConn("ctrl_i", "ctrl_i"), PortConn("done_o", "done")]
    return design


def test_a_control_pin_and_its_edges_have_the_control_colour(with_control):
    dot = schematic.internal_dot(with_control, "top")
    attrs = dot.split('"p__ctrl_i" [')[1].split("]")[0]
    assert C_CTRL in attrs, "the pin shows that the signal is control"
    assert f'color="{C_CTRL}"' in dot, "the edges show which module it controls"
    assert 'style="dashed"' in dot


def test_a_flag_pin_has_the_status_colour(with_control):
    dot = schematic.internal_dot(with_control, "top")
    attrs = dot.split('"p__flags_o" [')[1].split("]")[0]
    assert C_STATUS in attrs


def test_a_status_net_between_two_instances_is_coloured(with_control):
    dot = schematic.internal_dot(with_control, "top")
    attrs = dot.split('"n__done" [')[1].split("]")[0]
    assert C_STATUS in attrs
    assert f'color="{C_STATUS}"' in dot


def test_a_data_net_keeps_the_plain_style(with_control):
    dot = schematic.internal_dot(with_control, "top")
    attrs = dot.split('"n__mid" [')[1].split("]")[0]
    assert C_CTRL not in attrs and C_STATUS not in attrs
    assert '"i__i_a" -> "n__mid";' in dot, "a data edge carries no style"


def test_the_rules_of_the_project_colour_a_net(design):
    design.conventions = {"control": ["^weird$"]}
    top = design.modules["top"]
    top.instances[0].conns.append(PortConn("w_o", "weird"))
    top.instances[1].conns.append(PortConn("w_i", "weird"))
    dot = schematic.internal_dot(design, "top")
    attrs = dot.split('"n__weird" [')[1].split("]")[0]
    assert C_CTRL in attrs, "the rule of the code base decides the kind"


# -- the logic of the module itself ------------------------------------------


def test_a_control_net_with_one_end_connects_to_the_logic(design):
    """`streamer_ctrl` in a HWPE top joins one instance and the FSM of the
    module. The FSM is not an instance, thus the logic node stands for it."""
    design.modules["top"].instances[0].conns.append(PortConn("a_i", "stage_cfg"))
    dot = schematic.internal_dot(design, "top")
    assert '"l__logic"' in dot
    assert f'"l__logic" -> "n__stage_cfg" [color="{C_CTRL}", style="dashed"];' in dot


def test_a_status_port_that_only_the_logic_drives_gets_a_pin(design):
    """`assign evt_o = flags.evt` gives the port no instance. It still shows."""
    design.modules["top"].ports.append(Port("evt_o", "out"))
    dot = schematic.internal_dot(design, "top")
    assert '"p__evt_o"' in dot
    assert '"l__logic" -> "p__evt_o"' in dot


def test_no_logic_node_without_a_lonely_control_net(design):
    assert "l__logic" not in schematic.internal_dot(design, "top")


# -- generate blocks ---------------------------------------------------------


def test_a_generate_block_becomes_its_own_cluster(design):
    design.modules["top"].instances[0].gen_block = "gen_stage"
    dot = schematic.internal_dot(design, "top")
    assert '"cluster_gen_gen_stage"' in dot
    assert 'label="gen_stage"' in dot


# -- the symbol of a leaf module ---------------------------------------------


def test_the_symbol_shows_a_leaf_module_with_its_pins(design):
    dot = schematic.symbol_dot(design, "adder")
    assert '"m__adder"' in dot
    assert '"p__a_i"' in dot and '"p__sum_o"' in dot
    assert "clk_i" not in dot and "rst_ni" not in dot
    assert '"p__a_i" -> "m__adder"' in dot
    assert '"m__adder" -> "p__sum_o"' in dot


def test_the_symbol_of_a_module_with_no_ports_is_empty(design):
    design.modules["bare"] = Module(name="bare", package="demo_ip")
    assert schematic.symbol_dot(design, "bare") == ""


def test_the_symbol_labels_an_interface_pin_with_its_modport(design):
    design.modules["adder"].ports.append(
        Port("bus", "interface", is_interface=True, interface="demo_if",
             modport="master"))
    dot = schematic.symbol_dot(design, "adder")
    assert f'label="bus", fillcolor="{C_IFACE}"' in dot
    assert 'label="master"' in dot
