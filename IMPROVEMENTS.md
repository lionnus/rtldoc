# RTLDoc: verification and future work

## Verification

Tested end to end against a real Bender project (a HWPE accelerator with 17
dependencies). The following works today:

- `bender script flist-plus` and `bender sources -f` are read for the source set,
  include directories, defines, and the package each file belongs to.
- slang elaborates every module declared by the root package, including modules
  with macro-defined parameters and SV interface ports that do not elaborate as
  plain tops. 70 modules were extracted (37 owned by the root package), 0 errors.
- Also verified against upstream PULP repositories: `opope` (41 units, 14
  dependency packages) and `datamover` (20 units, 3 HWPE/HCI interfaces) run in
  CI; `cv32e40p` vega_v1.3.4 (26 units), `common_cells` v1.40.0 (117 units) and
  `axi` v0.39.10 (144 units, 7 interfaces) were verified by hand - all with zero
  diagnostics. Recent `cv32e40p` tags are not usable: their `Bender.yml` has an
  unresolvable `tech_cells_generic` requirement and lists two files that no
  longer exist.
- `bender` failures (an unresolvable dependency, a stale `sources` list) are
  reported with bender's own message and exit code 4, instead of being reduced to
  "no modules extracted". cv32e40p's `master` is an example of both.
- Elaborated units keep their declaration kind, so interfaces (`AXI_BUS`,
  `AXI_LITE`, ...) are presented and coloured as interfaces rather than modules.
- Ports carry resolved direction, type and bit width; parameters carry resolved
  values; instances are collected through generate blocks and arrays; interface
  connections resolve to the connected stream/bus instance and its modport.
- The static site builds: hierarchy graph, package graph, per-module internal
  connectivity diagrams, search index, light and dark themes.
- Packaging is verified: `uv build` produces a wheel that bundles the templates,
  CSS, JS and fonts; installing the wheel into a clean environment and running
  `rtldoc build` from the installed entry point reproduces the full site.

### Building the docs

`rtldoc gen` is the supported way to generate the documentation. It requires
`bender` and Graphviz (`dot`) on the `PATH`; the slang compiler ships with the
`pyslang` dependency. To wire it into a project, add a target that runs it (see
the `docs` example in the README) or run it as a CI job that publishes the output
directory to Pages.

`rtldoc check <dir>` examines the result and gives exit code 1 if it is not
complete. A design that no longer elaborates gives a site with no module and no
error, thus a pipeline that only runs `gen` cannot see the failure. The two
workflows of this repository use the same command as a user does.

### Project ergonomics

- The project root is found by walking up to the nearest `Bender.yml`, so the tool
  works from any subdirectory.
- Output defaults to `.rtldoc/` in the project root, and the first build adds
  that directory to the repository `.gitignore`.
- A build marks its output directory with `.rtldoc-build.json`; `gen` refuses to
  clean a non-empty directory without that marker unless `--force` is given, and
  only removes files matching its own naming scheme.
- The search index is a script that each page loads, thus the search works over
  `file://` too, where a page cannot `fetch()` a file. It was in each page: on
  pulp-platform/axi that is 47 kB in each of 220 pages, which made the site 10 MB
  larger than it is now.
- The graphs answer to a pinch and to a drag with two fingers. The CSS gives one
  finger to the browser (`touch-action: pan-x pan-y`), thus the page still scrolls
  and a tap still opens a node.
- Below 860 px the side bar goes away and each column gets `min-width: 0`. Without
  that, a grid column keeps the width of its widest content and the page scrolls
  to the side. A wide table scrolls in its own box.
- `rtldoc.yml` (optional, written by `rtldoc init`) sets the output
  directory, extra tops and the display name, so `make docs` needs no flags.

### The release

- A tag `v0.1.0` starts the `release` workflow. That workflow runs ruff and the
  tests again, builds the wheel and the source distribution, installs the wheel
  and runs it, and then publishes. PyPI keeps each version for ever, thus a
  broken build must not go out.
- PyPI trusts the workflow through OpenID Connect (Trusted Publishing). There is
  no API token in the repository, and no secret to rotate. The `pypi` and
  `testpypi` environments hold that trust.
- The version is in `rtldoc/__init__.py` only. `pyproject.toml` reads it with
  `[tool.hatch.version]`, and the workflow stops if the tag gives another value.
- A manual start of the workflow publishes to TestPyPI. Thus you can see the page
  of the project before the true release.

### Dependencies

- `bender` and Graphviz are external programs; `rtldoc doctor` reports both,
  and `gen` fails fast (exit 3) when bender is missing instead of rendering an
  empty site.
- `pyslang` is pinned to `>=11,<12`. Releases 8-10 expose `pyslang.Driver` with a
  different command-line API and silently extract zero modules; 11 moved it to
  `pyslang.driver`. The floor is enforced in `pyproject.toml` and reported by
  `doctor`.
- Python 3.9-3.13 are exercised in CI, matching the versions pyslang ships wheels
  for.

### Automated testing

- `tests/` drives the CLI end to end against a fixture design with a stub bender,
  so the suite needs no bender installation and runs anywhere.
- The `integration` workflow runs the real thing against `pulp-platform/opope`
  (an outer-product engine with 14 dependencies) and `pulp-platform/datamover`
  (an HWPE accelerator), pinned to commits, and asserts a floor on what is
  extracted (module and interface counts, named units, zero diagnostics, graphs
  rendered). Building it caught the interface-classification bug below and the
  swallowed bender errors.
- Coverage is measured with pytest-cov (statements and branches). It is 97%; the
  minimum is in `pyproject.toml` and CI enforces it. Codecov reports the coverage
  of each pull request.
- The tests were examined with a mutation experiment: 31 faults were put into the
  code on purpose, one at a time, and the tests found all of them. The first
  round of that experiment found six gaps (the side-bar order, the search index,
  the interface instances, the pages of a dependency module, the localparam
  filter and the comment length), which now have tests.
- A project in a directory with a space in its name now works: slang divides a
  command file at each space, so each entry gets quotation marks.

### The comment above a module

- `driver.syntaxTrees` gives the parsed files that the elaboration already made.
  Thus the tool reads the comments from the parser, and not with a regular
  expression: a `/** */` block, a `//` block, and a comment before an `import`
  each work.
- slang attaches a comment to the token that follows it. A PULP file has the
  licence block, then the documentation block, then often an import, then the
  module. The extractor collects the blocks of each member and gives the last
  one to the next module. A block that gives the licence is left out.
- A comment with a directive or a role is reStructuredText. A comment with a
  command that starts with `@` or with a backslash is Doxygen: `@brief`, `@param`
  and `@note` become Markdown, then the usual renderer makes the HTML. Doxygen
  has no parser for SystemVerilog, thus only its comment style is common: `///`
  and `//!` open a documentation line, and `/*!` opens a block.
  On pulp-platform/hwpe-stream, 33 of the 41 modules give a comment, and
  `hwpe_stream_source` gives 5.7 kB of reStructuredText.
- A name of a module in the comment becomes a link. The PULP comments write the
  name in bold, Markdown writes it in backticks; both work.
- A comment can come from an `include` file. `hci_helpers.svh` ends with
  ``` `endif /* `ifndef __HCI_HELPERS__ */ ```, and the HCI and common_cells
  modules took that as their description. The extractor now compares the file of
  each comment with the file of the module.
- The comment of an HCI module is above the `include`, and slang puts it in the
  trivia of that directive. Thus the extractor opens each directive. With the two
  corrections, pulp-platform/axi gives 120 comments in place of 97, and the
  datamover gives 12 in place of 6.
- A block that names the authors only is not a description, thus it is left out.

### The code of each file

- Pygments makes the colours and the line numbers. A page shows one file, because
  a file can have thousands of lines. The page of a module opens the code at its
  line, as Sphinx `viewcode`, Doxygen and rustdoc do.
- Only the root package gives pages. `bender checkout` puts the dependencies in
  the project, thus the package decides which file to show, and not the path. The
  code of a dependency has another licence and stays in its own repository.
- A file with more than 6000 lines keeps its page, but without the colours,
  because the lexer is slow on a large file. A file of more than 4 MB gets no page.
- The pages operate without Pygments. The tool then writes the same table, with
  the line numbers but with no colours.

### The graphs

- The colour of a pin gives the kind, and the shape gives the direction. Blue is
  an input, magenta an output, green an interface and orange no direction. These
  are the colours of the port table, thus the graph and the table agree.
- The kind of a signal has a colour and an edge style, thus the data path and
  the control plane separate. A control signal (`ctrl`, `cfg`, `en`, `sel`, ...)
  is amber and dashed; the arrows of its edges show which module controls what.
  A flag or status signal (`flags`, `busy`, `done`, `evt`, ...) is violet and
  dashed: the answer that control receives. The common tokens are in `naming`,
  and the match is per word part, thus `len_i` is not an enable. Each code base
  names these signals in its own way, thus `conventions:` in `rtldoc.yml` gives
  extra regular expressions per kind; a rule of the project comes before the
  common tokens, and a rule that does not compile is ignored. The port table
  marks the same ports with the same rules, thus the two agree.
- An interface edge is wide and green: a stream or a bus is the data path, not
  one wire. The modport of each connection labels its edge, thus a
  `hwpe_stream` shows `source → sink` — the direction of the data — by name and
  by arrow.
- The overview shows each top (at most four) with the same block diagram as its
  module page, thus the first page and the page of a module read the same way.
  One legend template serves both pages.
- A control or status net that touches one instance only keeps its single end:
  its other side is the logic of the module itself, drawn as one dashed node.
  On the datamover, the FSM of `datamover_top` drives `streamer_ctrl` and reads
  `streamer_flags`; without that node, the whole control plane of the module was
  invisible, because a net with one instance is not a connection between two
  instances. A control or status port that only an `assign` drives (`evt_o`)
  gets its pin the same way. Data nets keep the two-ends rule, because a
  dangling data net is noise.
- A module with no child instance gets the symbol view: one block with its pins
  around it, with the same colours and the modport on each interface edge. Thus
  each page of the site has a drawing, and a leaf like `hci_core_assign` shows
  `target → module → initiator` at a glance.
- A named generate block is a dashed cluster inside the module, thus
  `use_fifo_gen` in the datamover streamer reads as one optional group. A plain
  instance array stays one node with `xN`.
- The branch of an `if`-generate that the parameters did not take is dropped:
  slang keeps its symbols, but `isUninstantiated` marks them. Before this rule,
  the streamer showed the FIFO path and the no-FIFO path at the same time, as if
  both existed.
- An instance of a module that no source declares (an `UninstantiatedDefSymbol`)
  is in the model as a black box, with its port names and its nets. Before, it
  was a hole: `demo_missing_cell` was not even a node.
- The direction of a logic port comes from the declaration. An interface port
  has no direction in the language: the modport gives it first, because the
  compiler checked the modport, and the name (`_i`, `_in`, `_o`, `_out`) decides
  only when there is no modport. On the HWPE streamer,
  `hwpe_stream_intf_stream.source data_in` is an output; the name says the
  other way, thus a name-first rule drew the stream on the wrong side. A port
  that gives neither is a hexagon: the signals go in two directions.
- `cds` draws about two thirds of the height of its node and `hexagon` draws the
  full height. Each pin gets the height that makes the two the same.
- A node opens what it shows: an instance opens the module, an interface port and
  an interface signal open the interface, and a file opens the code.
- An element of an instance array has no name of its own. The extractor takes the
  name from the array, thus `hci_core_intf virt_tcdm [1:0] (...)` and a module
  array are in the model. Before this, they were not.

### Written documentation

- The tool reads `README.md`, and the Markdown and reStructuredText files in
  `doc/`, `docs/` and `documentation/`. It writes them as pages of the same site.
- `.readthedocs.yaml` gives one more directory. `configuration: conf.py` means the
  root of the repository, and then only the files directly in the root are read.
- docutils reads the reStructuredText. It cannot run a Sphinx extension: a
  `wavedrom`, `svprettyplot` or `toctree` directive gives no output, and a `raw`
  directive is stopped for the same reason as the HTML in a Markdown file.
  Verified against the 8 pages of pulp-platform/hwpe-doc: each one renders, with
  no error block in the output.
- A page with the name of a module attaches to that module. `axi/doc/axi_xbar.md`
  and the module `axi_xbar` link to each other. On pulp-platform/axi, 7 of the 9
  pages attach in this way.
- In the text, a `code` element with the name of a module or a package becomes a
  link. The images are copied into the site. The links between the pages point at
  the new names.
- The HTML in a Markdown file is escaped, not written into the page.
- The file graph shows each source file and the files that it needs.

### The package layout

- 18 modules, each with one subject, and no module above 400 lines. The layers
  are in the docstring of `rtldoc/__init__.py`, from `naming` and `model` at
  the bottom to `cli` at the top.
- `tests/test_architecture.py` reads the imports of each module and stops a
  module that imports from a higher layer. Before this rule, `deps` imported
  `extract` to find out if pyslang was usable; `deps` now makes that test itself.
- `rtldoc.build_documentation` and `rtldoc.check_site` give the two
  commands to another program. `__getattr__` imports on demand, thus
  `rtldoc --version` does not load pyslang.
- The splits: `naming` (the rules that read a name) out of `model`; `comments`
  (the comment above a unit) out of `extract`; `markup` (Markdown,
  reStructuredText and Doxygen) out of `docs`; `dot` (the colours, the DOT syntax
  and the Graphviz process) out of `graphs`; `schematic` (the inside of one
  module: the netlist view and the symbol view) out of `graphs`; `api` (the two
  steps) out of `cli`.

## Known limitations

- Clock and reset nets are detected by name pattern, not by tracing clock trees.
- A Sphinx extension does not run, so the output of `wavedrom`, `svprettyplot` and
  a similar directive is not in the page. A `:ref:` or `:numref:` role gives plain
  text, not a link.
- The `nav` of an `mkdocs.yml`, and the `toctree` of an `index.rst`, are not read.
  The pages are in the sequence of their paths, with the README first.
- `pulp-platform/hwpe-doc` is a repository of documentation only. It has no
  `Bender.yml`, thus this tool cannot run in it. The RTL of `hwpe-stream` and the
  text of `hwpe-doc` are in two repositories.
- Only modules reachable as a top of the root package (or reachable from one) are
  elaborated; dependency modules that are never instantiated appear as black boxes.
- Connection grouping uses the base signal name, so a bit-select and the full
  signal are treated as the same net.
- The kind of a signal comes from its name, not from its use. A control net with
  a name that says nothing (`q`, `word`) stays grey, and the internal-logic node
  appears only for a control or status net. Tracing use needs the processes.
- Each module elaborates as its own top with its default parameters, thus a
  module page shows the generate branch that the defaults take, which can differ
  from the branch a parent takes.

## Future ideas

### Visualising generate blocks (done)

Implemented as evaluated: each instance carries the name of the generate block
that holds it (`Instance.gen_block`), and the graph draws one dashed cluster per
named block inside the module boundary. A flat `xN` collapse stays for the
copies of a loop, thus a simple loop is still one node. The blocks of an
`if`-generate that the parameters did not take are dropped
(`isUninstantiated`). The resolved loop range and the branch condition are not
yet in the label; slang has them, and the label has room.

### Git: the commit of a module, and the diff of an interface (evaluated)

Possible: yes. Sensible: yes, in two separate steps.

**The commit of each module.** The project root is normally a git repository
(`project.git_root` finds it today). One `git log -1 --format=%h%x09%ad%x09%an
-- <file>` per source file gives the hash, the date and the author of the last
change. The module page then gets one more pill — `changed 2026-08-02 in
a1b2c3d` — and the pill can link to the commit in the web view of the host
(GitHub, GitLab), when `rtldoc.yml` gives the URL pattern. The cost is one git
call per file of the root package; a dependency stays out, because its checkout
often has no history. The layering fits: a new `gitinfo` module beside `bender`
reads the repository, the extractor stores the result in the model, and the
renderer shows it. `git blame` per port is possible with the line numbers that
the model has, but one blame per file is slow on a large repository — leave it
until someone asks.

**The diff of an interface.** `model.json` already holds each port with its
resolved type and width, each parameter value and each instance. A command
`rtldoc diff old-model.json new-model.json` compares two builds and reports the
modules whose boundary changed: a port added or removed, a width or a type
changed, a parameter default changed. That is the question a reviewer asks —
"did this change the interface?" — and CI can post the answer on a pull request.
The comparison needs no git and no elaboration of the old revision: the old
`model.json` comes from the last published site or from an artifact. A
`--fail-on-change` flag makes it a check. This is the natural first git-related
step, because the data is already there.

### Other ideas

- Clock and reset domain map: trace clock and reset nets across the hierarchy and
  show domains and crossings, instead of per-module name detection.
- Control tracing by connectivity: today the name gives the kind of a signal.
  The elaborated AST could give it instead — a net that drives only enable or
  select inputs is control by use, not by name. That removes the conventions
  from the model, at the cost of reading every process.
- A doc-site diff summary on the index page: "since the last build: 2 modules
  changed, 1 port added" — the last `model.json` is in the output directory
  before `gen` cleans it, thus the comparison is free.
- Bit-accurate connectivity: distinguish bit-selects and struct fields so partial
  connections are visible.
- Source links: link each module and port to its line in a repo web view.
- Config file: extend `rtldoc.yml` with package excludes and a theme setting
  (output, tops and name are supported today).
- Package pages with package contents: typedefs and parameters declared in a
  SystemVerilog package, not only the modules that belong to it.
- Incremental builds and parallel graph rendering for very large designs.
- Read the `nav` of `mkdocs.yml` and the `toctree` of `index.rst`, to give the
  pages the sequence that the author chose.
- One file (`rtldoc gen --single-file`) that holds the full site, to attach a
  design map to a review or to a mail. The site already operates offline. This step
  puts each module page in one document, and a hash gives the page.
- `rtldoc serve --watch`, which makes the documentation again when the RTL
  changes.
