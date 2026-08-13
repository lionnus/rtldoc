"""Makes the global graphs.

Each function gives Graphviz DOT for one view of the whole design: the
hierarchy, the Bender packages and the source files. A node contains a link,
thus the reader can move through the design. `schematic` draws the inside of
one module, and `dot` holds the colours, the DOT syntax and Graphviz.
"""

from __future__ import annotations

import html
import os

from .dot import (
    C_CLUSTER_LINE,
    C_DEP,
    C_DEP_TXT,
    C_OWNED,
    C_TOP,
    FONT_MONO,
    edge,
    header,
)
from .model import Design


def _mod_node(design: Design, name: str, *, focus: bool = False) -> str:
    mod = design.modules.get(name)
    owned = mod is not None and mod.package == design.root_package
    is_top = name in design.tops
    label = html.escape(name)
    if mod is None:
        # A black box has no page, thus its node carries no link.
        return ("[" + ", ".join([
            f'label="{label}"', f'tooltip="{label} (not extracted)"',
            f'fillcolor="{C_DEP}"', f'fontcolor="{C_DEP_TXT}"',
            'style="filled,dashed"', 'penwidth=1', f'color="{C_CLUSTER_LINE}"',
        ]) + "]")
    a = [f'label="{label}"', f'href="module-{name}.html"', 'target="_top"',
         f'tooltip="{label}"']
    if is_top or focus:
        a += [f'fillcolor="{C_TOP if is_top else C_OWNED}"', 'fontcolor="white"']
    elif owned:
        a += [f'fillcolor="{C_OWNED}"', 'fontcolor="white"']
    else:
        a += [f'fillcolor="{C_DEP}"', f'fontcolor="{C_DEP_TXT}"']
    return "[" + ", ".join(a) + "]"



def hierarchy_dot(design: Design, max_nodes: int = 140) -> str:
    roots = design.tops or [
        n for n, m in design.modules.items() if m.package == design.root_package
    ]
    lines = [header("LR")]
    seen: set[str] = set()
    edges: set[tuple[str, str]] = set()
    queue = list(roots)
    while queue and len(seen) < max_nodes:
        name = queue.pop(0)
        if name in seen:
            continue
        seen.add(name)
        mod = design.modules.get(name)
        if mod is None:
            continue
        for inst in mod.module_instances:
            edges.add((name, inst.module))
            if inst.module not in seen:
                queue.append(inst.module)
    for name in sorted(seen):
        lines.append(f'  "{name}" {_mod_node(design, name)};')
    for a, b in sorted(edges):
        lines.append(edge(a, b))
    lines.append("}")
    return "\n".join(lines)


def package_dot(design: Design) -> str:
    lines = [header("LR")]
    for name, pkg in sorted(design.packages.items()):
        fill = C_OWNED if pkg.root else C_DEP
        txt = "white" if pkg.root else C_DEP_TXT
        lines.append(
            f'  "{name}" [label="{html.escape(name)}", href="package-{name}.html", '
            f'target="_top", fillcolor="{fill}", fontcolor="{txt}"];'
        )
    for name, pkg in sorted(design.packages.items()):
        for dep in pkg.deps:
            if dep in design.packages:
                lines.append(edge(name, dep))
    lines.append("}")
    return "\n".join(lines)


def file_dot(design: Design, max_nodes: int = 120) -> str:
    """A graph of the source files of the root package and their connections.

    An edge goes from a file to each file that it needs. A file needs the file
    of a module that it instantiates, and the file of a package that it imports.
    Thus the graph gives the compile sequence and the structure of the
    repository.
    """
    file_of: dict[str, str] = {}
    for name, mod in design.modules.items():
        if mod.rel_file:
            file_of[name] = mod.rel_file

    owned = {
        mod.rel_file for mod in design.modules.values()
        if mod.rel_file and mod.package == design.root_package
    }
    if not owned:
        return ""

    edges: set = set()
    labels: dict = {}
    for mod in design.modules.values():
        src = mod.rel_file
        if src not in owned:
            continue
        for inst in mod.module_instances:
            dst = file_of.get(inst.module)
            if dst and dst != src:
                edges.add((src, dst))
        for inst in mod.interface_instances:
            dst = file_of.get(inst.module)
            if dst and dst != src:
                edges.add((src, dst))
    for f in owned:
        labels[f] = os.path.basename(f)
    for _, dst in edges:
        labels.setdefault(dst, os.path.basename(dst))

    keep = sorted(labels)[:max_nodes]
    kept = set(keep)

    # The node of a file opens the code of that file.
    urls = {s.rel_path: s.url for s in design.sources.values()}

    lines = [header("LR")]
    for f in keep:
        is_owned = f in owned
        fill = C_OWNED if is_owned else C_DEP
        txt = "white" if is_owned else C_DEP_TXT
        href = f'href="{urls[f]}", target="_top", ' if f in urls else ""
        lines.append(
            f'  "{f}" [{href}label="{html.escape(labels[f])}", '
            f'tooltip="{html.escape(f)}", shape=box, '
            f'fillcolor="{fill}", fontcolor="{txt}", fontname="{FONT_MONO}", fontsize=10];'
        )
    for a, b in sorted(edges):
        if a in kept and b in kept:
            lines.append(edge(a, b))
    lines.append("}")
    return "\n".join(lines)
