"""The global graphs: the hierarchy, the packages and the files."""

from __future__ import annotations

from conftest import needs_dot

from rtldoc import dot as dotlib
from rtldoc import graphs
from rtldoc.dot import C_DEP, C_OWNED, C_TOP, edge, render_dot
from rtldoc.model import Instance, Module, SourceFile


def test_hierarchy_graph_links_parent_to_child(design):
    dot = graphs.hierarchy_dot(design)
    assert '"top"' in dot and '"adder"' in dot
    assert '"top" -> "adder"' in dot
    assert "module-top.html" in dot, "nodes must be clickable"


def test_hierarchy_graph_respects_the_node_budget(design):
    dot = graphs.hierarchy_dot(design, max_nodes=1)
    assert dot.count("module-") <= 1


def test_hierarchy_visits_a_repeated_module_one_time(design):
    design.modules["top"].instances.append(
        Instance(name="i_c", module="adder", conns=[])
    )
    dot = graphs.hierarchy_dot(design)
    assert dot.count('"adder" [') == 1


def test_hierarchy_skips_a_top_that_was_not_extracted(design):
    design.tops.append("absent_top")
    dot = graphs.hierarchy_dot(design)
    assert '"absent_top" ->' not in dot


def test_package_graph_marks_the_root_and_its_dependencies(design):
    dot = graphs.package_dot(design)
    assert "package-demo_ip.html" in dot
    assert '"demo_ip" -> "common_cells"' in dot
    assert C_OWNED in dot, "the root package uses the accent colour"


@needs_dot
def test_render_dot_produces_svg(design):
    svg = render_dot(graphs.hierarchy_dot(design))
    assert svg is not None
    assert svg.lstrip().startswith("<svg")
    assert "adder" in svg


def test_render_dot_returns_none_without_graphviz(monkeypatch, design):
    monkeypatch.setattr(dotlib.shutil, "which", lambda _: None)
    assert render_dot(graphs.hierarchy_dot(design)) is None


def test_render_dot_returns_none_on_bad_dot(monkeypatch):
    monkeypatch.setattr(dotlib.shutil, "which", lambda _: "/usr/bin/dot")
    assert render_dot("this is not dot at all {{{") is None


# -- node styling ------------------------------------------------------------


def test_node_style_tells_the_module_classes_apart(design):
    design.modules["dep_mod"] = Module(name="dep_mod", package="common_cells")
    top = graphs._mod_node(design, "top")
    owned = graphs._mod_node(design, "adder")
    dep = graphs._mod_node(design, "dep_mod")
    unknown = graphs._mod_node(design, "never_elaborated")

    assert C_TOP in top, "a design top gets its own colour"
    assert C_OWNED in owned
    assert C_DEP in dep and "white" not in dep
    assert "dashed" in unknown, "a black box is drawn dashed"
    assert "href" not in unknown, "a black box has no page, thus no link"


def test_focus_highlights_a_module_that_is_not_a_top(design):
    assert C_OWNED in graphs._mod_node(design, "adder", focus=True)


def test_edges_carry_optional_labels_and_direction():
    assert edge("a", "b") == '  "a" -> "b";'
    assert 'label="net"' in edge("a", "b", label="net")
    assert "dir=none" in edge("a", "b", directed=False)


# -- the file graph ----------------------------------------------------------


def test_the_file_graph_joins_the_files_of_the_design(design):
    design.modules["top"].rel_file = "rtl/top.sv"
    design.modules["adder"].rel_file = "rtl/adder.sv"
    dot = graphs.file_dot(design)
    assert '"rtl/top.sv" -> "rtl/adder.sv"' in dot
    assert "top.sv" in dot and "adder.sv" in dot


def test_the_file_graph_marks_a_file_of_a_dependency(design):
    design.modules["top"].rel_file = "rtl/top.sv"
    design.modules["adder"].rel_file = "deps/adder.sv"
    design.modules["adder"].package = "common_cells"
    dot = graphs.file_dot(design)
    assert C_DEP in dot, "a file of a dependency has another colour"


def test_the_file_graph_needs_a_file_for_each_module(design):
    """Without the file of any module there is nothing to draw."""
    assert graphs.file_dot(design) == ""


def test_the_file_graph_has_no_edge_from_a_file_to_itself(design):
    design.modules["top"].rel_file = "rtl/all.sv"
    design.modules["adder"].rel_file = "rtl/all.sv"
    assert '"rtl/all.sv" -> "rtl/all.sv"' not in graphs.file_dot(design)


def test_the_file_graph_opens_the_code_of_a_file(design):
    design.modules["top"].rel_file = "rtl/top.sv"
    design.modules["adder"].rel_file = "rtl/adder.sv"
    design.sources["src-rtl-top-sv"] = SourceFile(slug="src-rtl-top-sv",
                                                  rel_path="rtl/top.sv")
    dot = graphs.file_dot(design)
    assert 'href="src-rtl-top-sv.html"' in dot
    assert 'href="src-rtl-adder-sv.html"' not in dot, "that file has no page"
