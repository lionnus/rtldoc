"""Draws the inside of one module.

Two views. `internal_dot` gives the schematic of a module: the child instances,
the generate blocks, the boundary pins and the nets between them, with the data
path and the control plane in their own colours. `symbol_dot` gives the symbol
of a module with no child instance: one block with its pins. `graphs` gives the
global views, and `dot` holds the colours, the DOT syntax and Graphviz.
"""

from __future__ import annotations

import html
import re

from .dot import (
    C_CLUSTER,
    C_CLUSTER_LINE,
    C_CTRL,
    C_DEP,
    C_DEP_TXT,
    C_GEN,
    C_IFACE,
    C_IN,
    C_IO,
    C_NET,
    C_NET_TXT,
    C_OUT,
    C_OWNED,
    C_STATUS,
    FONT,
    FONT_MONO,
    IFACE_BOX,
    IFACE_PENWIDTH,
    NET_BOX,
    PIN_CDS,
    PIN_HEX,
    edge,
    header,
)
from .model import Design
from .naming import is_background, signal_kind


def _link(design: Design, unit: str) -> str:
    """The DOT attributes that make a node open the page of *unit*."""
    if not unit or unit not in design.modules:
        return ""
    return f'href="module-{unit}.html", target="_top", tooltip="{html.escape(unit)}", '



_IDENT = re.compile(r"[A-Za-z_]\w*")


def _net_base(expr: str) -> str:
    """The name of the net in a connection expression.

    Gives `` for a constant, a concatenation or a literal, because those are not
    a net that two instances share.
    """
    e = (expr or "").strip().lstrip("(").strip()
    if not e or e[0] in "'\"{0123456789":   # constants / concats / literals
        return ""
    m = _IDENT.match(e)
    return m.group(0) if m else ""


_DRIVER_MODPORTS = {"source", "initiator", "master", "mst", "out", "producer", "manager"}
_LOAD_MODPORTS = {"sink", "subordinate", "slave", "slv", "in", "consumer", "target"}


def _role(child, port: str) -> str:
    """driver / load / both for a child instance's port (by its declared dir)."""
    if child is None:
        return "both"
    for p in child.ports:
        if p.name == port:
            return {"in": "load", "out": "driver"}.get(p.direction, "both")
    return "both"


def _iface_role(modport: str) -> str:
    """driver / load / both for an interface connection (by its modport name)."""
    m = (modport or "").lower()
    if m in _DRIVER_MODPORTS:
        return "driver"
    if m in _LOAD_MODPORTS:
        return "load"
    return "both"


def _conn_role(conn, child) -> str:
    return _iface_role(conn.modport) if conn.is_interface else _role(child, conn.port)


def _edge_style(kind: str) -> dict:
    """How an edge of one signal kind is drawn.

    An interface is the data path: wide and green, and the arrow gives the
    direction of the data. Control and status make the control plane: dashed,
    and the arrow shows which module controls what. A plain wire stays grey.
    """
    if kind == "iface":
        return {"color": C_IFACE, "penwidth": IFACE_PENWIDTH}
    if kind == "control":
        return {"color": C_CTRL, "dashed": True}
    if kind == "status":
        return {"color": C_STATUS, "dashed": True}
    return {}


#: The signal kinds of the control plane.
_CTRL_KINDS = ("control", "status")

#: The node that stands for the processes of the module itself.
_LOGIC = "l__logic"


def _collect_nets(design: Design, mod) -> tuple[dict, dict]:
    """The nets of the instance connections: net -> [(node, role, modport)].

    The modport travels with each endpoint, thus a stream can label its edges
    with `source` and `sink`. The background nets - clock, reset, clear and
    test mode - stay out, because they touch each instance.
    """
    nets: dict[str, list[tuple[str, str, str]]] = {}
    inst_ids: dict[str, str] = {}
    for inst in mod.module_instances:
        nid = f"i__{inst.name}"
        inst_ids[inst.name] = nid
        child = design.modules.get(inst.module)
        for c in inst.conns:
            base = _net_base(c.net)
            if base and not is_background(base):
                nets.setdefault(base, []).append(
                    (nid, _conn_role(c, child), c.modport if c.is_interface else ""))
    return nets, inst_ids


def _boundary_ports(mod, nets: dict, conventions: dict) -> dict:
    """The ports that become pins, added to *nets* as endpoints.

    A port joins the net that has its name. A control or status port with no
    such net still gets a pin, because its other side is the logic of the
    module itself - `evt_o` that an `assign` drives would otherwise not appear.
    """
    boundary: dict[str, dict] = {}
    for p in mod.ports:
        if is_background(p.name):
            continue
        if p.name not in nets and (
                p.is_interface
                or signal_kind(p.name, conventions) not in _CTRL_KINDS):
            continue
        d = p.graph_dir
        role = "driver" if d == "in" else ("load" if d == "out" else "both")
        boundary[p.name] = {
            "dir": d,
            "iface": p.interface if p.is_interface else "",
            "is_iface": p.is_interface,
        }
        nets.setdefault(p.name, []).append((f"p__{p.name}", role, p.modport))
    return boundary


def _net_kinds(design: Design, mod, nets: dict, boundary: dict) -> tuple[dict, dict]:
    """The kind of each net: the data path, the control plane, or a plain wire."""
    iface_of = {i.name: i.module for i in mod.interface_instances}
    kinds = {}
    for net in nets:
        if net in iface_of or boundary.get(net, {}).get("is_iface"):
            kinds[net] = "iface"
        else:
            kinds[net] = signal_kind(net, design.conventions)
    return kinds, iface_of


def _pin_shape(direction: str) -> str:
    """The pin of a port. The shape gives the direction, thus a hexagon - a
    point at each end - is a port that goes in two directions."""
    if direction == "in":
        return f"{PIN_CDS}, "
    if direction == "out":
        return f"{PIN_CDS}, orientation=180, "
    return f"{PIN_HEX}, "


def _pin_fill(kind: str, direction: str) -> str:
    """The colour of a pin gives the kind; a data pin has the colour of its
    direction. The shape gives the direction either way."""
    named = {"iface": C_IFACE, "control": C_CTRL, "status": C_STATUS}
    if kind in named:
        return named[kind]
    return {"in": C_IN, "out": C_OUT}.get(direction, C_IO)


def _pin_node(design: Design, net: str, info: dict, kind: str) -> str:
    shape = _pin_shape(info["dir"])
    fill = _pin_fill("iface" if info["is_iface"] else kind, info["dir"])
    return (
        f'"p__{net}" [{shape}{_link(design, info["iface"])}'
        f'label="{html.escape(net)}", fillcolor="{fill}", fontcolor="white", '
        "fontsize=10];"
    )


#: The invisible anchors that hold the two pin columns in place.
_A_IN, _A_OUT = "a__in", "a__out"
_ANCHOR = '[shape=point, width=0, height=0, style=invis];'


def _pin_columns(design: Design, kept: list, boundary: dict,
                 kinds: dict) -> tuple[list[str], list[str]]:
    """The pins, in two columns that hug the module box.

    One `rank` group per side keeps each column together: the inputs stand at
    the left edge of the box, the outputs and the two-way ports at the right
    edge. A rank alone does not hold against a cluster - Graphviz ranks the
    contents of the box past `rank=max` - thus each group carries an invisible
    anchor, `_wall_lines` ties every inner node between the two anchors, and
    `newrank` makes the rank hold across the cluster boundary. All three are
    necessary. Gives (lines, sides): the sides that exist, for the wall.
    """
    ins = [n for n in kept if n in boundary and boundary[n]["dir"] == "in"]
    outs = [n for n in kept if n in boundary and boundary[n]["dir"] != "in"]
    lines: list[str] = []
    sides: list[str] = []
    for rank, anchor, nets_of_side in (("min", _A_IN, ins), ("max", _A_OUT, outs)):
        if not nets_of_side:
            continue
        sides.append(anchor)
        lines.append(f"  {{ rank={rank};")
        lines.append(f'    "{anchor}" {_ANCHOR}')
        for net in nets_of_side:
            lines.append("    " + _pin_node(design, net, boundary[net], kinds[net]))
        lines.append("  }")
        # A flat chain from the anchor through the pins stacks the column: the
        # pins stand under one another, near the anchor, not across the canvas.
        chain = [anchor] + [f"p__{n}" for n in nets_of_side]
        for a, b in zip(chain, chain[1:]):
            lines.append(f'  "{a}" -> "{b}" [style=invis];')
    return lines, sides


def _wall_lines(inner: list[str], sides: list[str]) -> list[str]:
    """Invisible edges that keep each inner node between the two pin columns.

    Without them, a wire from an early instance to a pin gives the pin an
    early rank, and the pin floats in the middle of the canvas.
    """
    lines: list[str] = []
    for node in inner:
        if _A_IN in sides:
            lines.append(f'  "{_A_IN}" -> "{node}" [style=invis, weight=4];')
        if _A_OUT in sides:
            lines.append(f'  "{node}" -> "{_A_OUT}" [style=invis, weight=4];')
    return lines


def _instance_lines(design: Design, insts: list, inst_ids: dict,
                    max_nodes: int) -> list[str]:
    """The instance nodes, grouped in one sub-cluster per generate block."""
    groups: dict[str, list] = {}
    for inst in insts[:max_nodes]:
        groups.setdefault(inst.gen_block, []).append(inst)
    lines: list[str] = []
    for block, members in groups.items():
        if block:
            lines.append(f'    subgraph "cluster_gen_{block}" {{')
            lines.append(
                f'      label="{html.escape(block)}"; labeljust=l; fontsize=9; '
                f'fontcolor="{C_NET_TXT}"; style="filled,dashed"; '
                f'fillcolor="{C_GEN}"; color="{C_CLUSTER_LINE}"; margin=10;'
            )
        for inst in members:
            lbl = html.escape(inst.name)
            sub = html.escape(inst.module) + (f" x{inst.count}" if inst.count > 1 else "")
            href = "" if inst.unknown else f'href="module-{inst.module}.html", target="_top", '
            m = design.modules.get(inst.module)
            owned = m is not None and m.package == design.root_package
            fill = C_OWNED if owned else C_DEP
            txt = "white" if owned else C_DEP_TXT
            lines.append(
                f'    "{inst_ids[inst.name]}" [{href}'
                f'label=<<b>{lbl}</b><br/><font point-size="8">{sub}</font>>, '
                f'fillcolor="{fill}", fontcolor="{txt}"];'
            )
        if block:
            lines.append("    }")
    return lines


def _logic_node_line(name: str) -> str:
    """The node for the processes of *name*: the FSM and the assignments that
    drive or read a control net. Without it, that side of the net is invisible."""
    return (
        f'    "{_LOGIC}" [shape=box, style="filled,dashed", fillcolor="{C_NET}", '
        f'color="{C_CLUSTER_LINE}", penwidth=1, fontcolor="{C_NET_TXT}", '
        f'label=<internal logic<br/><font point-size="8">of {html.escape(name)}</font>>, '
        "fontsize=10];"
    )


def _wire_lines(nets: dict, kept: list, boundary: dict, kinds: dict) -> list[str]:
    """Drivers point into the signal (or the pin), signals point out to their
    loads. The kind of the net styles the edge, and the modport of an interface
    connection labels it, thus a stream shows its direction and its two sides.

    A net with one end only connects to the logic of the module: the arrow
    keeps its sense, thus the graph shows what that logic controls and reads.
    """
    lines: list[str] = []
    for net in kept:
        is_pin = net in boundary
        is_in_pin = is_pin and boundary[net]["dir"] == "in"
        is_out_pin = is_pin and not is_in_pin
        hub = f"p__{net}" if is_pin else f"n__{net}"
        style = _edge_style(kinds[net])
        if is_pin:
            style = {**style, "weight": 6}
        ends: dict[tuple[str, str], str] = {}
        for node, role, modport in nets[net]:
            if not node.startswith("p__"):
                ends.setdefault((node, role), modport)
        for (node, role), modport in sorted(ends.items()):
            label = modport if kinds[net] == "iface" else ""
            # A wire that runs against the side of its pin - a driver into an
            # input pin, a load out of an output pin - must not rank the pin,
            # or it fights the column and Graphviz gives up on both.
            if role == "driver":
                lines.append(edge(node, hub, label=label,
                                  constraint=not is_in_pin, **style))
            elif role == "load":
                lines.append(edge(hub, node, label=label,
                                  constraint=not is_out_pin, **style))
            else:
                lines.append(edge(hub, node, label=label, directed=False,
                                  constraint=not is_pin, **style))
        if len({n for n, _, _ in nets[net]}) < 2:
            # One end only: the other side is the logic of the module.
            roles = {r for _, r, _ in nets[net]}
            if roles == {"driver"}:
                lines.append(edge(hub, _LOGIC, constraint=not is_out_pin, **style))
            elif roles == {"load"}:
                lines.append(edge(_LOGIC, hub, constraint=not is_in_pin, **style))
            else:
                lines.append(edge(_LOGIC, hub, directed=False,
                                  constraint=not is_pin, **style))
    return lines


def internal_dot(design: Design, name: str, max_nodes: int = 240) -> str:
    """Schematic of *name*: child instances + the signals wiring them together."""
    mod = design.modules[name]
    insts = mod.module_instances
    if not insts:
        return ""

    nets, inst_ids = _collect_nets(design, mod)
    boundary = _boundary_ports(mod, nets, design.conventions)
    kinds, iface_of = _net_kinds(design, mod, nets, boundary)

    # A data net with one end only is not a connection: it stays out. A control
    # or status net keeps its single end, because its other side is the logic
    # of the module itself - the FSM that no instance shows.
    nets = {n: eps for n, eps in nets.items()
            if len({e[0] for e in eps}) >= 2 or kinds[n] in _CTRL_KINDS}
    kept = sorted(nets)[:max_nodes]
    lonely = [n for n in kept if len({e[0] for e in nets[n]}) < 2]

    lines = [header("LR", newrank=True)]
    # The module itself is the enclosing block. The ports stand inside it, at
    # its walls: the input rail at the left edge, the output rail at the right
    # edge, the submodules and the signals between the rails. Thus the frame
    # owns its ports, and a wire from a rail to an instance runs inside the
    # frame instead of around it.
    lines.append(f'  subgraph "cluster_{name}" {{')
    lines.append(
        f'    label="{html.escape(name)}"; labeljust=l; fontname="{FONT}"; '
        f'fontsize=12; fontcolor="{C_NET_TXT}"; style=filled; '
        f'fillcolor="{C_CLUSTER}"; color="{C_CLUSTER_LINE}"; penwidth=1.6; '
        "margin=28;"
    )
    pin_lines, sides = _pin_columns(design, kept, boundary, kinds)
    lines += ["  " + ln for ln in pin_lines]
    lines += _instance_lines(design, insts, inst_ids, max_nodes)
    if lonely:
        lines.append(_logic_node_line(name))
    for net in kept:
        if net not in boundary:
            iface = iface_of.get(net, "")
            shape = IFACE_BOX if kinds[net] == "iface" else NET_BOX
            fill = {"iface": C_IFACE, "control": C_CTRL,
                    "status": C_STATUS}.get(kinds[net], C_NET)
            txt = C_NET_TXT if fill == C_NET else "white"
            lines.append(
                f'    "n__{net}" [{shape}, {_link(design, iface)}'
                f'label="{html.escape(net)}", fillcolor="{fill}", fontcolor="{txt}", '
                f'fontname="{FONT_MONO}", fontsize=9];'
            )
    lines.append("  }")
    inner = list(inst_ids.values()) + [f"n__{n}" for n in kept if n not in boundary]
    if lonely:
        inner.append(_LOGIC)
    lines += _wall_lines(inner, sides)
    lines += _wire_lines(nets, kept, boundary, kinds)
    lines.append("}")
    return "\n".join(lines)


def symbol_dot(design: Design, name: str, max_ports: int = 60) -> str:
    """The symbol of *name*: one block with its pins around it.

    A module with no child instance still has a boundary. This graph gives that
    boundary the same look as the internal view: the colour of a pin gives the
    kind, the shape gives the direction, and the modport labels the edge.
    """
    mod = design.modules[name]
    ports = [p for p in mod.ports if not is_background(p.name)]
    if not ports:
        return ""
    owned = mod.package == design.root_package
    body = f"m__{name}"
    # An interface keeps its slanted shape and its colour, thus the symbol of
    # `hci_core_intf` cannot be read as the symbol of a module.
    if mod.kind == "interface":
        shape, fill, txt = "shape=parallelogram, ", C_IFACE, "white"
    else:
        shape = ""
        fill = C_OWNED if owned else C_DEP
        txt = "white" if owned else C_DEP_TXT
    lines = [header("LR")]
    lines.append(
        f'  "{body}" [{shape}label=<<b>{html.escape(name)}</b>>, '
        f'fillcolor="{fill}", fontcolor="{txt}", margin="0.35,0.25"];'
    )
    sides = {"min": [], "max": []}
    wires: list[str] = []
    for p in ports[:max_ports]:
        kind = ("iface" if p.is_interface
                else signal_kind(p.name, design.conventions))
        d = p.graph_dir
        pin = f"p__{p.name}"
        iface = p.interface if p.is_interface else ""
        sides["min" if d == "in" else "max"].append(
            f'"{pin}" [{_pin_shape(d)}{_link(design, iface)}'
            f'label="{html.escape(p.name)}", fillcolor="{_pin_fill(kind, d)}", '
            'fontcolor="white", fontsize=10];'
        )
        style = _edge_style(kind)
        label = p.modport if p.is_interface else ""
        if d == "in":
            wires.append(edge(pin, body, label=label, **style))
        elif d == "out":
            wires.append(edge(body, pin, label=label, **style))
        else:
            wires.append(edge(body, pin, label=label, directed=False, **style))
    for rank, nodes in sides.items():
        if nodes:
            lines.append(f"  {{ rank={rank};")
            lines += ["    " + n for n in nodes]
            lines.append("  }")
    lines += wires
    lines.append("}")
    return "\n".join(lines)
