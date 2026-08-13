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
    IFACE_PENWIDTH,
    NET_BOX,
    PIN_CDS,
    PIN_HEX,
    edge,
    header,
)
from .model import Design
from .naming import is_clock, is_reset, signal_kind


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
    with `source` and `sink`. The clock and the reset nets stay out.
    """
    nets: dict[str, list[tuple[str, str, str]]] = {}
    inst_ids: dict[str, str] = {}
    for inst in mod.module_instances:
        nid = f"i__{inst.name}"
        inst_ids[inst.name] = nid
        child = design.modules.get(inst.module)
        for c in inst.conns:
            base = _net_base(c.net)
            if base and not (is_clock(base) or is_reset(base)):
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
        if is_clock(p.name) or is_reset(p.name):
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


def _pin_line(design: Design, net: str, info: dict, kind: str) -> str:
    rank = "min" if info["dir"] == "in" else "max"
    shape = _pin_shape(info["dir"])
    fill = _pin_fill("iface" if info["is_iface"] else kind, info["dir"])
    return (
        f'  {{ rank={rank}; "p__{net}" [{shape}{_link(design, info["iface"])}'
        f'label="{html.escape(net)}", fillcolor="{fill}", fontcolor="white", '
        "fontsize=10]; }"
    )


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
        hub = f"p__{net}" if net in boundary else f"n__{net}"
        style = _edge_style(kinds[net])
        ends: dict[tuple[str, str], str] = {}
        for node, role, modport in nets[net]:
            if not node.startswith("p__"):
                ends.setdefault((node, role), modport)
        for (node, role), modport in sorted(ends.items()):
            label = modport if kinds[net] == "iface" else ""
            if role == "driver":
                lines.append(edge(node, hub, label=label, **style))
            elif role == "load":
                lines.append(edge(hub, node, label=label, **style))
            else:
                lines.append(edge(hub, node, label=label, directed=False, **style))
        if len({n for n, _, _ in nets[net]}) < 2:
            # One end only: the other side is the logic of the module.
            roles = {r for _, r, _ in nets[net]}
            if roles == {"driver"}:
                lines.append(edge(hub, _LOGIC, **style))
            elif roles == {"load"}:
                lines.append(edge(_LOGIC, hub, **style))
            else:
                lines.append(edge(_LOGIC, hub, directed=False, **style))
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

    lines = [header("LR")]
    # Boundary ports sit outside the module block, like external pins. A pin
    # doubles as the hub for its net, so no separate signal node is drawn.
    for net in kept:
        if net in boundary:
            lines.append(_pin_line(design, net, boundary[net], kinds[net]))
    # The module itself is the enclosing block; submodules and signals nest inside.
    lines.append(f'  subgraph "cluster_{name}" {{')
    lines.append(
        f'    label="{html.escape(name)}"; labeljust=l; fontname="{FONT}"; '
        f'fontsize=11; fontcolor="{C_NET_TXT}"; style=filled; '
        f'fillcolor="{C_CLUSTER}"; color="{C_CLUSTER_LINE}"; margin=14;'
    )
    lines += _instance_lines(design, insts, inst_ids, max_nodes)
    if lonely:
        lines.append(_logic_node_line(name))
    for net in kept:
        if net not in boundary:
            iface = iface_of.get(net, "")
            fill = {"iface": C_IFACE, "control": C_CTRL,
                    "status": C_STATUS}.get(kinds[net], C_NET)
            txt = C_NET_TXT if fill == C_NET else "white"
            lines.append(
                f'    "n__{net}" [{NET_BOX}, {_link(design, iface)}'
                f'label="{html.escape(net)}", fillcolor="{fill}", fontcolor="{txt}", '
                f'fontname="{FONT_MONO}", fontsize=9];'
            )
    lines.append("  }")
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
    ports = [p for p in mod.ports if not (is_clock(p.name) or is_reset(p.name))]
    if not ports:
        return ""
    owned = mod.package == design.root_package
    body = f"m__{name}"
    lines = [header("LR")]
    lines.append(
        f'  "{body}" [label=<<b>{html.escape(name)}</b>>, '
        f'fillcolor="{C_OWNED if owned else C_DEP}", '
        f'fontcolor="{"white" if owned else C_DEP_TXT}", margin="0.35,0.25"];'
    )
    for p in ports[:max_ports]:
        kind = ("iface" if p.is_interface
                else signal_kind(p.name, design.conventions))
        d = p.graph_dir
        pin = f"p__{p.name}"
        iface = p.interface if p.is_interface else ""
        lines.append(
            f'  {{ rank={"min" if d == "in" else "max"}; "{pin}" '
            f"[{_pin_shape(d)}{_link(design, iface)}"
            f'label="{html.escape(p.name)}", fillcolor="{_pin_fill(kind, d)}", '
            'fontcolor="white", fontsize=10]; }'
        )
        style = _edge_style(kind)
        label = p.modport if p.is_interface else ""
        if d == "in":
            lines.append(edge(pin, body, label=label, **style))
        elif d == "out":
            lines.append(edge(body, pin, label=label, **style))
        else:
            lines.append(edge(body, pin, label=label, directed=False, **style))
    lines.append("}")
    return "\n".join(lines)
