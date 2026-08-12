"""The naming conventions of a SystemVerilog design.

SystemVerilog does not say which port is a clock, which reset is active-low, or
which side of an interface a modport is. The RTL communities use the name of the
port for that. These functions hold each of those rules in one place, thus the
model, the graphs and the pages agree.

Each function takes a name and gives a name. Nothing here reads the design.
"""

from __future__ import annotations

import re

#: The modport names that make an interface an output of a module.
OUT_MODPORTS = {"source", "initiator", "master", "mst", "out", "producer", "manager"}

#: The modport names that make an interface an input of a module.
IN_MODPORTS = {"sink", "subordinate", "slave", "slv", "in", "consumer", "target"}

#: The name endings that give a direction. The longer ending comes first.
DIR_SUFFIX = (("_in", "in"), ("_out", "out"), ("_i", "in"), ("_o", "out"))

#: The name parts of a control signal: one module sets the behaviour of another.
CTRL_TOKENS = {
    "ctrl", "cfg", "config", "cmd", "mode", "sel", "en", "enable",
    "start", "stop", "clear", "flush", "trigger",
}

#: The name parts of a flag or status signal: the answer that control receives.
STATUS_TOKENS = {
    "flag", "flags", "status", "busy", "done", "err", "error",
    "evt", "event", "irq", "interrupt",
}

_TOKEN_SPLIT = re.compile(r"[^a-z]+")


def is_clock(name: str) -> bool:
    n = name.lower()
    return "clk" in n or "clock" in n


def is_reset(name: str) -> bool:
    n = name.lower()
    return "rst" in n or "reset" in n


def interface_dir(modport: str) -> str:
    """The direction of an interface port, from the name of its modport."""
    m = (modport or "").lower()
    if m in OUT_MODPORTS:
        return "out"
    if m in IN_MODPORTS:
        return "in"
    return "inout"


def name_direction(name: str) -> str:
    """The direction that the name of a port gives, or `` if it gives none."""
    n = name.lower()
    for suffix, direction in DIR_SUFFIX:
        if n.endswith(suffix):
            return direction
    return ""


def signal_kind(name: str, conventions: dict | None = None) -> str:
    """`control`, `status` or `` for a signal, from its name.

    *conventions* gives the rules of one code base, from `rtldoc.yml`:
    ``{"control": [regex, ...], "status": [regex, ...]}``. A rule of the project
    comes before the common tokens. A rule that is not a valid regular
    expression is ignored, thus a bad settings file cannot stop a build.
    """
    n = (name or "").lower()
    for kind in ("control", "status"):
        for pattern in (conventions or {}).get(kind, []):
            try:
                if re.search(pattern, n):
                    return kind
            except re.error:
                continue
    tokens = set(_TOKEN_SPLIT.split(n))
    if tokens & STATUS_TOKENS:
        return "status"
    if tokens & CTRL_TOKENS:
        return "control"
    return ""


def reset_polarity(name: str) -> str:
    """The polarity of a reset port, from its name."""
    n = name.lower()
    if re.search(r"(rst|reset)_?n", n) or n.endswith("n") or n.endswith("ni") or "_nb" in n:
        return "active-low"
    if re.search(r"(rst|reset)_?b", n) or n.endswith("b"):
        return "active-low"
    return "active-high"
