"""The parts of the renderer that the end-to-end tests do not examine."""

from __future__ import annotations

import json

from rtldoc import render
from rtldoc.model import Design, Instance, Module, Port, PortConn


def test_responsive_svg_drops_the_fixed_size():
    svg = '<svg width="120pt" height="80pt" viewBox="0 0 120 80"><g/></svg>'
    out = render._responsive(svg)
    assert 'width="120pt"' not in out
    assert 'height="80pt"' not in out
    assert 'viewBox="0 0 120 80"' in out, "the viewBox must survive so CSS can scale it"
    assert 'class="rtld-graph"' in out


def test_responsive_passes_through_a_missing_graph():
    assert render._responsive(None) is None


def test_inline_json_cannot_close_the_script_element():
    """A module with the name `</script>` must not close the data element."""
    payload = {"modules": [{"name": "</script><img src=x>"}]}
    out = render._json_for_script(payload)
    assert "</script>" not in out
    assert "<" not in out and ">" not in out
    assert json.loads(out)["modules"][0]["name"] == "</script><img src=x>"


def test_direction_badges_are_short():
    assert render._dirbadge("in") == "in"
    assert render._dirbadge("inout") == "io"
    assert render._dirbadge("interface") == "if"
    assert render._dirbadge("something_else") == "something_else"


def _design() -> Design:
    d = Design(root_package="demo", project_root="/demo", tops=["top"])
    d.modules["top"] = Module(
        name="top", package="demo",
        ports=[Port("ctrl_i", "in"), Port("y_o", "out", width=8)],
        instances=[
            Instance(name="i_a", module="leaf", conns=[
                PortConn("c_i", "ctrl_i"), PortConn("q_o", "y_o"),
            ]),
        ],
    )
    d.modules["leaf"] = Module(name="leaf", package="demo",
                               ports=[Port("c_i", "in"), Port("q_o", "out")])
    return d


def test_the_overview_shows_each_top_with_the_module_diagram(tmp_path, monkeypatch):
    """The first page and the page of a module read the same way."""
    monkeypatch.setattr(render, "render_dot",
                        lambda dot: '<svg width="1" height="1"><g/></svg>')
    r = render.Renderer(_design(), str(tmp_path))
    r._render_index()
    page = (tmp_path / "index.html").read_text()
    assert "Structure of" in page
    assert 'href="module-top.html"' in page
    assert "control" in page, "the legend explains the control colour"


def test_the_overview_without_graphviz_has_no_structure_section(tmp_path, monkeypatch):
    monkeypatch.setattr(render, "render_dot", lambda dot: None)
    r = render.Renderer(_design(), str(tmp_path))
    r._render_index()
    assert "Structure of" not in (tmp_path / "index.html").read_text()


def test_the_port_table_marks_a_control_port(tmp_path, monkeypatch):
    monkeypatch.setattr(render, "render_dot", lambda dot: None)
    r = render.Renderer(_design(), str(tmp_path))
    r._render_module("top")
    page = (tmp_path / "module-top.html").read_text()
    assert "kind-control" in page and ">ctrl</span>" in page


def test_the_page_names_the_instantiation_it_shows(tmp_path, monkeypatch):
    monkeypatch.setattr(render, "render_dot", lambda dot: None)
    design = _design()
    design.modules["leaf"].elab_context = "top.i_a"
    r = render.Renderer(design, str(tmp_path))
    r._render_module("leaf")
    page = (tmp_path / "module-leaf.html").read_text()
    assert "as top.i_a" in page


def test_the_port_table_marks_with_the_rules_of_the_project(tmp_path, monkeypatch):
    monkeypatch.setattr(render, "render_dot", lambda dot: None)
    design = _design()
    design.conventions = {"status": [r"^y_"]}
    r = render.Renderer(design, str(tmp_path))
    r._render_module("top")
    page = (tmp_path / "module-top.html").read_text()
    assert "kind-status" in page and ">flag</span>" in page
