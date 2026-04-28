import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

try:
    from pyverilog.vparser.ast import (
        Always,
        Assign,
        BlockingSubstitution,
        Identifier,
        IfStatement,
        IntConst,
        Lvalue,
        ModuleDef,
        NonblockingSubstitution,
        Partselect,
        Pointer,
        Rvalue,
    )
    from pyverilog.vparser.parser import parse as pyverilog_parse
except Exception:
    pyverilog_parse = None


class Logger:
    def __init__(self, filename: Path) -> None:
        self.terminal = sys.stdout
        self.log = open(filename, "w", encoding="utf-8")

    def write(self, message: str) -> None:
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

    def flush(self) -> None:
        self.terminal.flush()
        self.log.flush()


@dataclass
class ProjectPaths:
    base_path: Path
    golden_rtl: Path
    buggy_netlist: Path
    testbench: Path
    output_dir: Path
    lib_files: List[Path]
    golden_files: List[Path]
    buggy_support_files: List[Path]
    project_label: str
    golden_include_dirs: List[Path]
    buggy_rtl_dir: Optional[Path] = None
    buggy_behavioral_files: Optional[List[Path]] = None


@dataclass
class Assignment:
    lhs: str
    rhs: str
    lhs_base: str
    rhs_signals: Set[str]
    start: int
    end: int
    source_text: str


@dataclass
class ModuleInfo:
    module_name: str
    outputs: Set[str]
    assignments: List[Assignment]
    source: str
    path: Path


@dataclass
class SimulationResult:
    ok: bool
    returncode: int
    stdout: str
    compile_cmd: List[str]
    run_cmd: List[str]


@dataclass
class SimulationAssessment:
    passed: bool
    mismatch_detected: bool
    success_detected: bool
    summary: str


@dataclass
class RepairAttempt:
    name: str
    candidate_path: Path
    target_count: int
    result: SimulationResult
    assessment: SimulationAssessment
    failure_context: str
    minimality_score: Optional[Dict[str, int]] = None
    syntax_attempts: int = 1
    executor_mode: str = "codex"


@dataclass
class CodexSession:
    command: List[str]


@dataclass
class FeasibilityReport:
    status: str
    reason: str
    supported_mode: str
    details: List[str]
    confidence: int


@dataclass
class CellInstance:
    cell_type: str
    instance_name: str
    ports: Dict[str, str]
    src_file: Optional[str]
    src_line: Optional[int]


@dataclass
class PortInfo:
    name: str
    direction: str
    declaration: str


@dataclass
class SequentialSignature:
    clock_ports: List[str]
    reset_ports: List[str]
    sequential: bool


SIGNAL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_$]*)\b")
ASSIGN_RE = re.compile(r"assign\s+(.+?)\s*=\s*(.+?)\s*;", re.DOTALL)
COMMENT_RE = re.compile(r"//.*?$|/\*.*?\*/", re.DOTALL | re.MULTILINE)
KEYWORDS = {
    "assign",
    "module",
    "endmodule",
    "input",
    "output",
    "wire",
    "reg",
    "logic",
    "begin",
    "end",
    "if",
    "else",
    "case",
    "for",
    "generate",
    "genvar",
    "parameter",
}
CELL_INSTANCE_RE = re.compile(r"^\s*([A-Z][A-Z0-9_]*_X[0-9]+)\s+\S+\s*\(", re.MULTILINE)
SRC_LINE_RE = re.compile(r'src\s*=\s*"[^"]*/([^"/]+):(\d+)\.\d+-\d+\.\d+"')
PORT_CONN_RE = re.compile(r"\.(\w+)\((.*?)\)")


def discover_single_file(directory: Path, extensions: Sequence[str]) -> Path:
    files = [
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in extensions
    ]
    if not files:
        raise FileNotFoundError(f"No supported file found in {directory}")
    if len(files) > 1:
        files.sort()
        print(f"[WARN] Multiple files found in {directory}; using {files[0].name}")
    return files[0]


def discover_verilog_files(directory: Path) -> List[Path]:
    if not directory.exists():
        return []
    return sorted(
        path
        for path in directory.rglob("*")
        if path.is_file()
        and path.suffix.lower() in (".v", ".sv")
        and "patched_netlist" not in path.parts
        and "__pycache__" not in path.parts
    )


def ensure_output_dir(base_path: Path) -> Path:
    preferred = base_path / "patched_netlist"
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        probe = preferred / ".codex_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return preferred
    except OSError:
        fallback = Path(__file__).resolve().parent / "patched_netlist" / base_path.name
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def normalize_local_path(path: Path) -> Path:
    return Path(os.path.normpath(str(path))).resolve()


def pick_preferred_file(files: Sequence[Path], preferred_names: Sequence[str]) -> Path:
    lower_map = {path.name.lower(): path for path in files}
    for name in preferred_names:
        match = lower_map.get(name.lower())
        if match is not None:
            return match
    return sorted(files)[0]


def normalize_variant_name(raw: Optional[str], prefix: str) -> Optional[str]:
    if raw is None:
        return None
    token = raw.strip()
    if token.startswith(prefix):
        return token
    if token.startswith("v") and token[1:].isdigit():
        return f"{prefix}{token[1:]}"
    if token.isdigit():
        return f"{prefix}{token}"
    return token


def discover_project_paths(project_root: Optional[str] = None, bug_variant: Optional[str] = None) -> ProjectPaths:
    base_path = Path(project_root).resolve() if project_root else Path(__file__).resolve().parent
    golden_files = discover_verilog_files(base_path / "golden_rtl")
    buggy_files = discover_verilog_files(base_path / "buggy_netlist")

    if not golden_files:
        raise FileNotFoundError(f"No Verilog files found under {base_path / 'golden_rtl'}")
    if not buggy_files:
        raise FileNotFoundError(f"No Verilog files found under {base_path / 'buggy_netlist'}")

    normalized_bug_variant = normalize_variant_name(bug_variant, "aes_bug_v")
    buggy_root = base_path / "buggy_netlist"
    tb_root = base_path / "tb"

    if normalized_bug_variant and (buggy_root / normalized_bug_variant).exists():
        variant_dir = buggy_root / normalized_bug_variant
        variant_files = discover_verilog_files(variant_dir)
        if not variant_files:
            raise FileNotFoundError(f"No Verilog files found under {variant_dir}")
        buggy_netlist = pick_preferred_file(variant_files, ("1_synth.v", "1_1_yosys.v"))
        buggy_support = [path for path in variant_files if path != buggy_netlist]
        tb_variant_name = normalized_bug_variant.replace("aes_bug_", "buggy_")
        tb_dir = tb_root / tb_variant_name
        if not tb_dir.exists():
            raise FileNotFoundError(f"Expected testbench directory not found: {tb_dir}")
        testbench = discover_single_file(tb_dir, (".v", ".sv"))
        project_label = normalized_bug_variant
        buggy_rtl_dir = base_path / "buggy_rtl" / normalized_bug_variant
    else:
        buggy_netlist = pick_preferred_file(buggy_files, ("1_synth.v", "arith_unit_bug.v"))
        buggy_support = [path for path in buggy_files if path != buggy_netlist]
        testbench = discover_single_file(tb_root, (".v", ".sv"))
        project_label = "default"
        buggy_rtl_dir = None

    golden_rtl = pick_preferred_file(golden_files, (buggy_netlist.stem + ".v", "aes_cipher_top.v", "arith_unit.v"))

    output_dir = ensure_output_dir(base_path)

    lib_dir = base_path / "lib"
    lib_files = discover_verilog_files(lib_dir)

    golden_support = [path for path in golden_files if path != golden_rtl]
    golden_include_dirs = sorted({path.parent for path in golden_files})
    buggy_behavioral_files = discover_verilog_files(buggy_rtl_dir) if buggy_rtl_dir and buggy_rtl_dir.exists() else None
    return ProjectPaths(
        base_path=base_path,
        golden_rtl=golden_rtl,
        buggy_netlist=buggy_netlist,
        testbench=testbench,
        output_dir=output_dir,
        lib_files=lib_files,
        golden_files=[golden_rtl] + golden_support,
        buggy_support_files=buggy_support,
        project_label=project_label,
        golden_include_dirs=golden_include_dirs,
        buggy_rtl_dir=buggy_rtl_dir if buggy_rtl_dir and buggy_rtl_dir.exists() else None,
        buggy_behavioral_files=buggy_behavioral_files,
    )


def build_project_paths_from_explicit_inputs(
    golden_rtl: Path,
    buggy_netlist: Path,
    testbench: Optional[Path],
    project_root: Optional[str] = None,
    lib_dirs: Optional[Sequence[str]] = None,
    lib_files: Optional[Sequence[str]] = None,
    golden_support_dirs: Optional[Sequence[str]] = None,
    buggy_support_dirs: Optional[Sequence[str]] = None,
    buggy_rtl_dir: Optional[str] = None,
) -> ProjectPaths:
    golden_rtl = normalize_local_path(golden_rtl)
    buggy_netlist = normalize_local_path(buggy_netlist)
    output_dir: Optional[Path] = None
    if testbench is not None:
        testbench = normalize_local_path(testbench)
    if project_root:
        base_path = Path(project_root).resolve()
    else:
        roots = [str(golden_rtl.parent), str(buggy_netlist.parent)]
        if testbench is not None:
            roots.append(str(testbench.parent))
        base_path = Path(os.path.commonpath(roots)).resolve()
    output_dir = ensure_output_dir(base_path)
    if testbench is None:
        testbench = output_dir / "auto_generated_tb.v"

    golden_support_files: List[Path] = []
    for support_dir in golden_support_dirs or []:
        golden_support_files.extend(discover_verilog_files(normalize_local_path(Path(support_dir))))
    golden_support_files = [path for path in unique_paths(golden_support_files + [golden_rtl]) if path != golden_rtl]

    buggy_support_files: List[Path] = []
    for support_dir in buggy_support_dirs or []:
        buggy_support_files.extend(discover_verilog_files(normalize_local_path(Path(support_dir))))
    buggy_support_files = [path for path in unique_paths(buggy_support_files + [buggy_netlist]) if path != buggy_netlist]

    resolved_lib_files: List[Path] = []
    for directory in lib_dirs or []:
        resolved_lib_files.extend(discover_verilog_files(normalize_local_path(Path(directory))))
    for file_path in lib_files or []:
        path = normalize_local_path(Path(file_path))
        if path.exists():
            resolved_lib_files.append(path)
    resolved_lib_files = unique_paths(resolved_lib_files)

    resolved_buggy_rtl_dir = normalize_local_path(Path(buggy_rtl_dir)) if buggy_rtl_dir else None
    buggy_behavioral_files = (
        discover_verilog_files(resolved_buggy_rtl_dir)
        if resolved_buggy_rtl_dir is not None and resolved_buggy_rtl_dir.exists()
        else None
    )

    golden_files = [golden_rtl] + golden_support_files
    return ProjectPaths(
        base_path=base_path,
        golden_rtl=golden_rtl,
        buggy_netlist=buggy_netlist,
        testbench=testbench,
        output_dir=output_dir,
        lib_files=resolved_lib_files,
        golden_files=golden_files,
        buggy_support_files=buggy_support_files,
        project_label="explicit-inputs",
        golden_include_dirs=sorted({path.parent for path in golden_files}),
        buggy_rtl_dir=resolved_buggy_rtl_dir if resolved_buggy_rtl_dir and resolved_buggy_rtl_dir.exists() else None,
        buggy_behavioral_files=buggy_behavioral_files,
    )


def recommended_project_layout() -> str:
    return """Recommended ECO Project Layout

project_root/
|-- golden_rtl/
|   |-- top.v
|   `-- support_files...
|-- buggy_netlist/
|   |-- top_netlist.v
|   `-- support_files...
|-- tb/
|   `-- tb_top.v
|-- lib/
|   `-- standard_cells.v
|-- buggy_rtl/                  # optional, used for reconstruction mode
|   `-- candidate_buggy_rtl...
`-- patched_netlist/            # auto-generated output directory

Optional Batch Layout

project_root/
`-- cases/
    |-- case_01/
    |   |-- golden_rtl/
    |   |-- buggy_netlist/
    |   |-- tb/
    |   `-- lib/
    `-- case_02/
        |-- golden_rtl/
        |-- buggy_netlist/
        |-- tb/
        `-- lib/

Recommended Output Layout

patched_netlist/
|-- feasibility_report.json
|-- feasibility_report.md
|-- reconstructed_rtl_summary.txt
|-- reconstructed_rtl_candidate.v
|-- patch_report.json
|-- patch_report.md
|-- <top>_patched.v
`-- logs/                      # optional future extension for batch runs

CLI Usage Styles

1. Auto-discovery from project_root:
   python ECO_Agent.py --project-root <project_root>

2. Explicit paths:
   python ECO_Agent.py --golden-file <golden.v> --buggy-file <buggy.v> --tb-file <tb.v> --lib-dir <lib_dir>

3. Analysis only:
   python ECO_Agent.py --check-only --project-root <project_root>
"""


def strip_comments(text: str) -> str:
    return COMMENT_RE.sub("", text)


def extract_module_name(text: str) -> str:
    match = re.search(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)\b", text)
    if not match:
        raise ValueError("Could not determine module name")
    return match.group(1)


def extract_outputs(text: str) -> Set[str]:
    clean = strip_comments(text)
    outputs: Set[str] = set()
    header_match = re.search(
        r"\bmodule\s+[A-Za-z_][A-Za-z0-9_$]*\s*\((.*?)\)\s*;",
        clean,
        re.DOTALL,
    )
    if header_match:
        header = header_match.group(1)
        for part in re.split(r",(?![^\[]*\])", header):
            piece = part.strip()
            if not piece.startswith("output"):
                continue
            piece = re.sub(r"^output\s+", "", piece)
            piece = re.sub(r"^(reg|wire|logic)\s+", "", piece)
            piece = re.sub(r"^\[[^\]]+\]\s*", "", piece)
            if piece:
                outputs.add(signal_base(piece))

    for match in re.finditer(r"\boutput\b\s+(?:reg|wire|logic\s+)?(?:\[[^\]]+\]\s+)?([^;]+);", clean):
        for part in match.group(1).split(","):
            name = part.strip()
            if not name:
                continue
            name = re.sub(r"^(reg|wire|logic)\s+", "", name)
            name = re.sub(r"^\[[^\]]+\]\s*", "", name)
            outputs.add(signal_base(name))
    return {name for name in outputs if name and name not in KEYWORDS and name not in {"input", "output", "inout"}}


def extract_port_list(text: str) -> List[str]:
    clean = strip_comments(text)
    match = re.search(
        r"\bmodule\s+[A-Za-z_][A-Za-z0-9_$]*\s*\((.*?)\)\s*;",
        clean,
        re.DOTALL,
    )
    if not match:
        raise ValueError("Could not extract module port list")
    raw = match.group(1)
    names: List[str] = []
    for part in re.split(r",(?![^\[]*\])", raw):
        piece = part.strip()
        if not piece:
            continue
        piece = re.sub(r"^(input|output|inout)\s+", "", piece)
        piece = re.sub(r"^(reg|wire|logic)\s+", "", piece)
        piece = re.sub(r"^\[[^\]]+\]\s*", "", piece)
        name = signal_base(piece)
        if name:
            names.append(name)
    return names


def extract_port_info(text: str) -> List[PortInfo]:
    clean = strip_comments(text)
    port_names = extract_port_list(text)
    info_map: Dict[str, PortInfo] = {}
    body_clean = clean
    header_match = re.search(
        r"\bmodule\s+[A-Za-z_][A-Za-z0-9_$]*\s*\((.*?)\)\s*;",
        clean,
        re.DOTALL,
    )
    if header_match:
        current_direction: Optional[str] = None
        current_prefix = ""
        for part in re.split(r",(?![^\[]*\])", header_match.group(1)):
            piece = part.strip()
            if not piece:
                continue
            direction_match = re.match(r"^(input|output|inout)\s+(.*)$", piece)
            if direction_match:
                current_direction = direction_match.group(1)
                remainder = direction_match.group(2).strip()
            else:
                remainder = piece

            if current_direction is None:
                continue

            tokens = remainder.split()
            if len(tokens) > 1:
                current_prefix = " ".join(tokens[:-1])
                name_token = tokens[-1]
            else:
                name_token = tokens[0]
            name = signal_base(name_token)
            prefix_text = f"{current_prefix} " if current_prefix else ""
            declaration = f"{current_direction} {prefix_text}{name_token};".replace("  ", " ").strip()
            info_map.setdefault(name, PortInfo(name=name, direction=current_direction, declaration=declaration))
        body_clean = clean[header_match.end():]

    for direction in ("input", "output", "inout"):
        pattern = re.compile(rf"\b{direction}\b\s+([^;]+);", re.DOTALL)
        for match in pattern.finditer(body_clean):
            declaration_body = match.group(1).strip()
            items = re.split(r",(?![^\[]*\])", declaration_body)
            prefix = items[0]
            prefix_tokens = prefix.split()
            shared_tokens = prefix_tokens[:-1]
            for item in items:
                item = item.strip()
                if not item:
                    continue
                name = signal_base(item.split()[-1])
                if len(items) == 1:
                    decl = f"{direction} {declaration_body};"
                else:
                    if item == items[0].strip():
                        decl = f"{direction} {item};"
                    else:
                        decl = f"{direction} {' '.join(shared_tokens)} {item};".replace("  ", " ").strip()
                info_map[name] = PortInfo(name=name, direction=direction, declaration=decl)

    ordered: List[PortInfo] = []
    for name in port_names:
        if name not in info_map:
            raise ValueError(f"Could not determine declaration for port '{name}'")
        ordered.append(info_map[name])
    return ordered


def wire_decl_from_port(port: PortInfo, suffix: str) -> str:
    declaration = re.sub(r"\breg\b", "", port.declaration)
    declaration = re.sub(r"\blogic\b", "", declaration)
    declaration = re.sub(r"^\s*output\b", "", declaration).strip().rstrip(";").strip()
    if declaration.endswith(port.name):
        declaration = declaration[: -len(port.name)].rstrip()
    prefix = f"{declaration} " if declaration else ""
    return f"wire {prefix}{port.name}{suffix};".replace("  ", " ").strip()


def signal_base(name: str) -> str:
    return name.split("[", 1)[0].strip()


def normalize_expr(expr: str) -> str:
    return re.sub(r"\s+", "", expr)


def expression_to_text(node: object) -> str:
    if node is None:
        return ""
    attr = getattr(node, "var", None)
    if attr is not None:
        return expression_to_text(attr)
    coord = getattr(node, "coord", None)
    if isinstance(node, Identifier):
        return node.name
    if isinstance(node, IntConst):
        return node.value
    if isinstance(node, Partselect):
        return f"{expression_to_text(node.var)}[{expression_to_text(node.msb)}:{expression_to_text(node.lsb)}]"
    if isinstance(node, Pointer):
        return f"{expression_to_text(node.var)}[{expression_to_text(node.ptr)}]"
    left = getattr(node, "left", None)
    right = getattr(node, "right", None)
    cond = getattr(node, "cond", None)
    true_value = getattr(node, "true_value", None)
    false_value = getattr(node, "false_value", None)
    operator = getattr(node, "__class__", type(node)).__name__
    if cond is not None and true_value is not None and false_value is not None:
        return f"({expression_to_text(cond)} ? {expression_to_text(true_value)} : {expression_to_text(false_value)})"
    if left is not None and right is not None:
        op_map = {
            "Plus": "+",
            "Minus": "-",
            "Times": "*",
            "And": "&",
            "Or": "|",
            "Xor": "^",
            "Xnor": "~^",
            "Land": "&&",
            "Lor": "||",
            "Eq": "==",
            "NotEq": "!=",
            "LessThan": "<",
            "GreaterThan": ">",
        }
        return f"({expression_to_text(left)} {op_map.get(operator, operator)} {expression_to_text(right)})"
    statement = str(node)
    if coord is not None and " at " in statement:
        statement = statement.split(" at ", 1)[0]
    return statement


def extract_signals(expr: str) -> Set[str]:
    signals = set()
    for token in SIGNAL_RE.findall(expr):
        if token not in KEYWORDS and not token.isdigit():
            signals.add(token)
    return signals


def parse_assignments_with_pyverilog(path: Path) -> List[Assignment]:
    if pyverilog_parse is None:
        return []
    try:
        ast, _ = pyverilog_parse([str(path)])
    except Exception:
        return []

    source = read_text_safe(path)
    assignments: List[Assignment] = []

    def append_assignment(lhs_text: str, rhs_text: str, source_text: str = "") -> None:
        lhs_text = lhs_text.strip()
        rhs_text = rhs_text.strip()
        if not lhs_text or not rhs_text:
            return
        assignments.append(
            Assignment(
                lhs=lhs_text,
                rhs=rhs_text,
                lhs_base=signal_base(lhs_text),
                rhs_signals=extract_signals(rhs_text),
                start=-1,
                end=-1,
                source_text=source_text or f"{lhs_text} = {rhs_text}",
            )
        )

    def walk(node: object) -> None:
        if isinstance(node, Assign):
            append_assignment(expression_to_text(node.left), expression_to_text(node.right), expression_to_text(node))
        elif isinstance(node, (BlockingSubstitution, NonblockingSubstitution)):
            append_assignment(expression_to_text(node.left), expression_to_text(node.right), expression_to_text(node))
        for child in getattr(node, "children", lambda: [])():
            walk(child)

    walk(ast)
    if assignments:
        return assignments
    return parse_assignments(source)


def parse_assignments(text: str) -> List[Assignment]:
    assignments: List[Assignment] = []
    for match in ASSIGN_RE.finditer(text):
        lhs = match.group(1).strip()
        rhs = match.group(2).strip()
        assignments.append(
            Assignment(
                lhs=lhs,
                rhs=rhs,
                lhs_base=signal_base(lhs),
                rhs_signals=extract_signals(rhs),
                start=match.start(),
                end=match.end(),
                source_text=match.group(0),
            )
        )
    return assignments


def parse_module(path: Path) -> ModuleInfo:
    source = path.read_text(encoding="utf-8")
    assignments = parse_assignments_with_pyverilog(path)
    if not assignments:
        assignments = parse_assignments(source)
    return ModuleInfo(
        module_name=extract_module_name(source),
        outputs=extract_outputs(source),
        assignments=assignments,
        source=source,
        path=path,
    )


def rename_top_module_source(source: str, new_name: str) -> str:
    return re.sub(
        r"(\bmodule\s+)([A-Za-z_][A-Za-z0-9_$]*)",
        rf"\1{new_name}",
        source,
        count=1,
    )


def detect_design_style(source: str) -> str:
    assign_count = len(ASSIGN_RE.findall(source))
    cell_instance_count = len(CELL_INSTANCE_RE.findall(source))
    if cell_instance_count > 20 and assign_count < 10:
        return "standard_cell_netlist"
    if re.search(r"\balways_comb\b", source):
        return "combinational_procedural"
    if assign_count > 0:
        return "assign_level"
    if re.search(r"\balways\s*@\s*\*", source):
        return "combinational_procedural"
    if re.search(r"\balways\s*@\s*\(", source):
        return "rtl_sequential"
    return "unknown"


def collect_missing_cell_types(text: str, available_libs: Sequence[Path]) -> List[str]:
    if not available_libs:
        available_modules: Set[str] = set()
    else:
        available_modules = set()
        for lib in available_libs:
            lib_text = lib.read_text(encoding="utf-8", errors="replace")
            available_modules.update(re.findall(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)\b", lib_text))

    used_cells = sorted(set(CELL_INSTANCE_RE.findall(text)))
    return [cell for cell in used_cells if cell not in available_modules]


def build_assignment_map(assignments: Sequence[Assignment]) -> Dict[str, Assignment]:
    return {assignment.lhs: assignment for assignment in assignments}


def build_driver_map(assignments: Sequence[Assignment]) -> Dict[str, List[Assignment]]:
    drivers: Dict[str, List[Assignment]] = {}
    for assignment in assignments:
        drivers.setdefault(assignment.lhs_base, []).append(assignment)
    return drivers


def backward_cone(target_bases: Set[str], assignments: Sequence[Assignment]) -> Set[str]:
    drivers = build_driver_map(assignments)
    pending = list(target_bases)
    seen: Set[str] = set()

    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        for assignment in drivers.get(current, []):
            for dep in assignment.rhs_signals:
                if dep not in seen:
                    pending.append(dep)
    return seen


def collect_output_assignments(module: ModuleInfo) -> Dict[str, Assignment]:
    return {
        assignment.lhs: assignment
        for assignment in module.assignments
        if assignment.lhs_base in module.outputs
    }


def get_suspicious_outputs(buggy: ModuleInfo, golden: ModuleInfo) -> Tuple[List[str], List[str]]:
    buggy_out = collect_output_assignments(buggy)
    golden_out = collect_output_assignments(golden)

    suspicious: List[str] = []
    reasons: List[str] = []

    all_lhs = sorted(set(buggy_out) | set(golden_out))
    for lhs in all_lhs:
        bug = buggy_out.get(lhs)
        gold = golden_out.get(lhs)
        if bug is None:
            suspicious.append(lhs)
            reasons.append(f"Missing output assignment in buggy netlist: {lhs}")
        elif gold is None:
            suspicious.append(lhs)
            reasons.append(f"Extra output assignment in buggy netlist: {lhs}")
        elif normalize_expr(bug.rhs) != normalize_expr(gold.rhs):
            suspicious.append(lhs)
            reasons.append(f"Output expression mismatch for {lhs}: buggy='{bug.rhs}' golden='{gold.rhs}'")

    if not suspicious:
        buggy_by_base = {assignment.lhs_base for assignment in buggy.assignments if assignment.lhs_base in buggy.outputs}
        golden_by_base = {assignment.lhs_base for assignment in golden.assignments if assignment.lhs_base in golden.outputs}
        for output_base in sorted((buggy.outputs | golden.outputs) & (buggy_by_base | golden_by_base)):
            suspicious.append(output_base)
            reasons.append(f"Falling back to whole-output analysis for {output_base}")

    return suspicious, reasons


def collect_cone_differences(
    buggy: ModuleInfo,
    golden: ModuleInfo,
    suspicious_bases: Set[str],
) -> List[str]:
    cone = backward_cone(suspicious_bases, buggy.assignments)
    buggy_map = build_assignment_map(buggy.assignments)
    golden_map = build_assignment_map(golden.assignments)
    candidate_lhs = sorted(
        lhs
        for lhs in set(buggy_map) | set(golden_map)
        if signal_base(lhs) in cone
    )

    diffs = []
    for lhs in candidate_lhs:
        bug = buggy_map.get(lhs)
        gold = golden_map.get(lhs)
        if bug is None or gold is None:
            diffs.append(lhs)
        elif normalize_expr(bug.rhs) != normalize_expr(gold.rhs):
            diffs.append(lhs)
    return diffs


def build_signal_graph(assignments: Sequence[Assignment]) -> Dict[str, Set[str]]:
    graph: Dict[str, Set[str]] = {}
    for assignment in assignments:
        graph.setdefault(assignment.lhs_base, set()).update(signal_base(dep) for dep in assignment.rhs_signals)
    return graph


def rank_bug_candidates(
    buggy: ModuleInfo,
    golden: ModuleInfo,
    suspicious_bases: Set[str],
) -> List[Tuple[str, int]]:
    cone = backward_cone(suspicious_bases, buggy.assignments)
    buggy_map = build_assignment_map(buggy.assignments)
    golden_map = build_assignment_map(golden.assignments)
    graph = build_signal_graph(buggy.assignments)
    scores: Counter[str] = Counter()
    for lhs in set(buggy_map) | set(golden_map):
        lhs_base = signal_base(lhs)
        if lhs_base not in cone:
            continue
        bug = buggy_map.get(lhs)
        gold = golden_map.get(lhs)
        if bug is None or gold is None:
            scores[lhs_base] += 5
        elif normalize_expr(bug.rhs) != normalize_expr(gold.rhs):
            scores[lhs_base] += 4
        scores[lhs_base] += len(graph.get(lhs_base, set()))
        if lhs_base in suspicious_bases:
            scores[lhs_base] += 3
    return scores.most_common(12)


def replace_assignments(
    source: str,
    original_assignments: Sequence[Assignment],
    replacements: Dict[str, str],
    removals: Set[str],
    additions: Sequence[str],
) -> str:
    new_source = source
    for assignment in sorted(original_assignments, key=lambda item: item.start, reverse=True):
        if assignment.lhs in removals:
            new_source = new_source[: assignment.start] + new_source[assignment.end :]
        elif assignment.lhs in replacements:
            new_source = (
                new_source[: assignment.start]
                + replacements[assignment.lhs]
                + new_source[assignment.end :]
            )

    if additions:
        endmodule_match = re.search(r"\bendmodule\b", new_source)
        if not endmodule_match:
            raise ValueError("Could not find endmodule while adding assignments")
        insertion = "\n    " + "\n    ".join(additions) + "\n\n"
        new_source = new_source[:endmodule_match.start()] + insertion + new_source[endmodule_match.start():]
    return new_source


def build_candidate_source(
    buggy: ModuleInfo,
    golden: ModuleInfo,
    target_lhs: Sequence[str],
) -> str:
    buggy_map = build_assignment_map(buggy.assignments)
    golden_map = build_assignment_map(golden.assignments)

    replacements: Dict[str, str] = {}
    removals: Set[str] = set()
    additions: List[str] = []

    for lhs in target_lhs:
        gold_assignment = golden_map.get(lhs)
        if gold_assignment is None:
            continue
        statement = f"assign {gold_assignment.lhs} = {gold_assignment.rhs};"
        if lhs in buggy_map:
            replacements[lhs] = statement
        else:
            additions.append(statement)
            for buggy_assignment in buggy.assignments:
                if buggy_assignment.lhs_base == gold_assignment.lhs_base:
                    removals.add(buggy_assignment.lhs)

        if "[" not in gold_assignment.lhs:
            for buggy_assignment in buggy.assignments:
                if (
                    buggy_assignment.lhs_base == gold_assignment.lhs_base
                    and buggy_assignment.lhs != gold_assignment.lhs
                ):
                    removals.add(buggy_assignment.lhs)

    return replace_assignments(buggy.source, buggy.assignments, replacements, removals, additions)


def write_candidate(path: Path, source: str) -> None:
    path.write_text(source, encoding="utf-8")


def rebuild_assign_only_module(
    buggy: ModuleInfo,
    golden: ModuleInfo,
    lhs_targets: Sequence[str],
) -> str:
    raw_buggy_assignments = parse_assignments(buggy.source) or buggy.assignments
    raw_golden_assignments = parse_assignments(golden.source) or golden.assignments
    target_bases = {signal_base(item) for item in lhs_targets}
    if not target_bases:
        target_bases = {assignment.lhs_base for assignment in raw_golden_assignments}
    golden_assigns = [
        assignment
        for assignment in raw_golden_assignments
        if assignment.lhs_base in target_bases
    ]
    preserved_buggy_assigns = [
        assignment
        for assignment in raw_buggy_assignments
        if assignment.lhs_base not in target_bases
    ]
    header_match = re.search(r"^\s*module\b.*?\);\s*", buggy.source, re.DOTALL)
    if header_match is None:
        return golden.source
    header = buggy.source[: header_match.end()]
    body_lines = []
    for assignment in preserved_buggy_assigns:
        body_lines.append(f"    {assignment.source_text.strip()}")
    for assignment in golden_assigns:
        body_lines.append(f"    {assignment.source_text.strip()}")
    body = "".join(f"\n{line}" for line in body_lines)
    return f"{header}{body}\nendmodule\n"


class Planner:
    def build_assign_level_strategies(
        self,
        buggy: ModuleInfo,
        golden: ModuleInfo,
        suspicious_outputs: Sequence[str],
        cone_diffs: Sequence[str],
    ) -> List[Tuple[str, List[str]]]:
        strategies: List[Tuple[str, List[str]]] = []
        if suspicious_outputs:
            strategies.append(("replace_mismatched_outputs", list(suspicious_outputs)))
        if cone_diffs:
            strategies.append(("replace_differing_assigns_in_cone", list(cone_diffs)))
        global_diffs = collect_cone_differences(
            buggy,
            golden,
            {assignment.lhs_base for assignment in buggy.assignments} | {signal_base(item) for item in suspicious_outputs},
        )
        if global_diffs:
            strategies.append(("replace_all_differing_assigns", global_diffs))
        return strategies


class HeuristicExecutor:
    def __init__(self, project: ProjectPaths) -> None:
        self.project = project

    def generate_assign_level_candidate(
        self,
        buggy: ModuleInfo,
        golden: ModuleInfo,
        lhs_targets: Sequence[str],
        failure_context: str = "",
    ) -> str:
        del failure_context
        return sanitize_candidate_source(
            rebuild_assign_only_module(buggy, golden, lhs_targets),
            expected_module=buggy.module_name,
        )


class CodexExecutor:
    def __init__(self, session: CodexSession, project: ProjectPaths) -> None:
        self.session = session
        self.project = project

    def build_prompt(
        self,
        buggy: ModuleInfo,
        golden: ModuleInfo,
        lhs_targets: Sequence[str],
        failure_context: str = "",
    ) -> str:
        targets = ", ".join(lhs_targets) if lhs_targets else "(none)"
        guidance = (
            "You are repairing a combinational Verilog netlist.\n"
            "Read the golden RTL, buggy netlist, and testbench from the provided absolute paths.\n"
            "Return only the complete corrected Verilog source for the buggy top module.\n"
            "Do not return markdown fences, explanations, bullets, or surrounding text.\n"
            "Preserve the original module name and keep edits minimal.\n"
            "Focus on combinational logic only.\n"
        )
        if failure_context:
            guidance += (
                "The previous candidate failed. Use this simulator/compiler feedback to correct the next attempt:\n"
                f"{failure_context}\n"
            )
        guidance += (
            f"Golden RTL path: {self.project.golden_rtl}\n"
            f"Buggy netlist path: {self.project.buggy_netlist}\n"
            f"Testbench path: {self.project.testbench}\n"
            f"Suspicious targets: {targets}\n"
            f"Golden module name: {golden.module_name}\n"
            f"Buggy module name: {buggy.module_name}\n"
        )
        return guidance

    def generate_assign_level_candidate(
        self,
        buggy: ModuleInfo,
        golden: ModuleInfo,
        lhs_targets: Sequence[str],
        failure_context: str = "",
    ) -> str:
        prompt = self.build_prompt(buggy, golden, lhs_targets, failure_context=failure_context)
        output_path = self.project.output_dir / "codex_last_message.txt"
        command = (
            self.session.command
            + [
                "exec",
                "--skip-git-repo-check",
                "--sandbox",
                "workspace-write",
                "-C",
                str(self.project.base_path),
                "-o",
                str(output_path),
                prompt,
            ]
        )
        result = run_command(command, self.project.base_path)
        combined = (result.stdout or "") + (result.stderr or "")
        if result.returncode != 0:
            raise RuntimeError(
                "Codex CLI execution failed.\n"
                f"Command: {' '.join(command)}\n"
                f"Output:\n{combined}"
            )
        if not output_path.exists():
            raise RuntimeError("Codex CLI did not produce an output message file")
        raw_source = output_path.read_text(encoding="utf-8", errors="replace")
        candidate_source = sanitize_candidate_source(raw_source, expected_module=buggy.module_name)
        if extract_verilog_module_block(candidate_source, expected_module=buggy.module_name) is None:
            raise RuntimeError(
                "Codex CLI did not return a valid Verilog module for the buggy top.\n"
                f"Expected module: {buggy.module_name}\n"
                f"Output:\n{raw_source}"
            )
        return candidate_source


class Verifier:
    def __init__(self, project: ProjectPaths, golden_stdout: Optional[str] = None) -> None:
        self.project = project
        self.golden_stdout = golden_stdout

    def run_candidate(
        self,
        candidate_path: Path,
        tag: str,
        support_files: Optional[Sequence[Path]] = None,
        include_dirs: Optional[Sequence[Path]] = None,
    ) -> Tuple[SimulationResult, SimulationAssessment, str]:
        result = run_simulation(candidate_path, self.project, tag, support_files=support_files, include_dirs=include_dirs)
        assessment = assess_simulation_output(result.stdout, golden_stdout=self.golden_stdout)
        failure_context = extract_failure_context(result.stdout)
        return result, assessment, failure_context


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def run_command(command: List[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def unique_paths(paths: Sequence[Path]) -> List[Path]:
    seen: Set[Path] = set()
    ordered: List[Path] = []
    for path in paths:
        resolved = normalize_local_path(path)
        if resolved in seen:
            continue
        seen.add(resolved)
        ordered.append(path)
    return ordered


def library_search_dirs(project: ProjectPaths) -> List[Path]:
    return unique_paths(path.parent for path in project.lib_files)


def resolve_codex_command() -> Optional[List[str]]:
    candidates = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "npm" / "codex.cmd")
        candidates.append(Path(appdata) / "npm" / "codex.exe")

    for name in ("codex.cmd", "codex.exe", "codex"):
        located = shutil.which(name)
        if located:
            candidates.append(Path(located))

    seen: Set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists():
            return [str(candidate)]
    return None


def run_interactive_command(command: List[str], cwd: Path) -> int:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    proc = subprocess.run(command, cwd=str(cwd), env=env)
    return proc.returncode


def prompt_for_codex_login(codex_command: List[str], cwd: Path, failure_output: str) -> None:
    print("[WARN] Codex CLI is installed but is not ready for non-interactive execution.")
    if failure_output.strip():
        print(summarize_sim_output(failure_output))
    print("[ACTION] This flow requires Codex CLI login on the local machine.")
    print(f"[ACTION] Run this command in the current terminal if login does not start automatically: {' '.join(codex_command + ['login'])}")
    response = input("Launch Codex login now? [Y/n]: ").strip().lower()
    if response not in {"", "y", "yes"}:
        raise EnvironmentError("Codex CLI login is required before running the ECO flow")
    run_interactive_command(codex_command + ["login"], cwd)
    input("Press Enter after Codex login completes...")


def ensure_codex_ready(project: ProjectPaths) -> CodexSession:
    codex_command = resolve_codex_command()
    if codex_command is None:
        raise EnvironmentError(
            "Codex CLI is not installed or not in PATH. Install Codex CLI and run `codex login` before using this ECO flow."
        )

    for attempt in range(2):
        status = run_command(codex_command + ["login", "status"], project.base_path)
        combined = (status.stdout or "") + (status.stderr or "")
        if status.returncode == 0:
            return CodexSession(command=codex_command)
        if attempt == 0:
            prompt_for_codex_login(codex_command, project.base_path, combined)

    raise EnvironmentError(
        "Codex CLI login could not be verified. Run `codex login` successfully on this machine and retry."
    )


def generate_testbench_with_codex(
    project: ProjectPaths,
    codex_session: CodexSession,
    golden: ModuleInfo,
    ports: Sequence[PortInfo],
    signature: SequentialSignature,
    cycle_count: int,
) -> Path:
    output_path = project.output_dir / "auto_generated_tb.v"
    input_ports = [port for port in ports if port.direction == "input"]
    output_ports = [port for port in ports if port.direction == "output"]
    prompt = (
        "Generate a complete self-checking Verilog/SystemVerilog testbench.\n"
        "Read the golden RTL from the provided absolute path and generate a testbench for the top module.\n"
        "The testbench must instantiate a DUT named exactly as the top module in the source file.\n"
        "The testbench should print [SUCCESS] when no mismatches are found and print MISMATCH lines on failure.\n"
        "Do not use markdown fences or explanation text. Return only testbench source.\n"
        f"Golden RTL path: {project.golden_rtl}\n"
        f"Top module: {golden.module_name}\n"
        f"Input ports: {', '.join(port.name for port in input_ports) or '(none)'}\n"
        f"Output ports: {', '.join(port.name for port in output_ports) or '(none)'}\n"
        f"Sequential design: {signature.sequential}\n"
        f"Clock ports: {', '.join(signature.clock_ports) or '(none)'}\n"
        f"Reset ports: {', '.join(signature.reset_ports) or '(none)'}\n"
        f"Requested randomized/directed cycles: {cycle_count}\n"
        "For combinational designs, randomize all non-clock inputs and compare outputs to a reference model computed from the golden RTL behavior as observed by directly instantiating the golden module.\n"
        "For sequential designs with one clock, generate a clock, apply reset, drive randomized inputs across multiple cycles, and compare DUT outputs against a golden reference instance cycle by cycle.\n"
        "Use a bounded run and call $finish.\n"
    )
    command = (
        codex_session.command
        + [
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            "workspace-write",
            "-C",
            str(project.base_path),
            "-o",
            str(output_path),
            prompt,
        ]
    )
    result = run_command(command, project.base_path)
    combined = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0 or not output_path.exists():
        raise RuntimeError(
            "Codex CLI failed to generate the automatic testbench.\n"
            f"Command: {' '.join(command)}\n"
            f"Output:\n{combined}"
        )
    output_path.write_text(sanitize_candidate_source(output_path.read_text(encoding="utf-8", errors="replace")), encoding="utf-8")
    return output_path


def run_simulation(
    design_file: Path,
    project: ProjectPaths,
    tag: str,
    support_files: Optional[Sequence[Path]] = None,
    include_dirs: Optional[Sequence[Path]] = None,
) -> SimulationResult:
    sim_output = project.output_dir / f"{tag}.out"
    compile_cmd = ["iverilog", "-g2012"]
    for include_dir in unique_paths(include_dirs or []):
        compile_cmd.extend(["-I", str(include_dir)])
    for lib_dir in library_search_dirs(project):
        compile_cmd.extend(["-y", str(lib_dir)])
    compile_cmd.extend(["-o", str(sim_output), str(project.testbench), str(design_file)])
    if support_files:
        compile_cmd.extend(str(path) for path in support_files)

    compile_proc = run_command(compile_cmd, project.output_dir)
    compile_stdout = (compile_proc.stdout or "") + (compile_proc.stderr or "")
    if compile_proc.returncode != 0:
        return SimulationResult(
            ok=False,
            returncode=compile_proc.returncode,
            stdout=compile_stdout,
            compile_cmd=compile_cmd,
            run_cmd=[],
        )

    run_cmd = ["vvp", str(sim_output)]
    run_proc = run_command(run_cmd, project.output_dir)
    runtime_stdout = (run_proc.stdout or "") + (run_proc.stderr or "")
    return SimulationResult(
        ok=run_proc.returncode == 0,
        returncode=run_proc.returncode,
        stdout=runtime_stdout,
        compile_cmd=compile_cmd,
        run_cmd=run_cmd,
    )


def run_compile_check(
    design_file: Path,
    project: ProjectPaths,
    tag: str,
    support_files: Optional[Sequence[Path]] = None,
    include_dirs: Optional[Sequence[Path]] = None,
) -> SimulationResult:
    sim_output = project.output_dir / f"{tag}.out"
    compile_cmd = ["iverilog", "-g2012"]
    for include_dir in unique_paths(include_dirs or []):
        compile_cmd.extend(["-I", str(include_dir)])
    for lib_dir in library_search_dirs(project):
        compile_cmd.extend(["-y", str(lib_dir)])
    compile_cmd.extend(["-o", str(sim_output), str(project.testbench), str(design_file)])
    if support_files:
        compile_cmd.extend(str(path) for path in support_files)
    compile_proc = run_command(compile_cmd, project.output_dir)
    compile_stdout = (compile_proc.stdout or "") + (compile_proc.stderr or "")
    return SimulationResult(
        ok=compile_proc.returncode == 0,
        returncode=compile_proc.returncode,
        stdout=compile_stdout,
        compile_cmd=compile_cmd,
        run_cmd=[],
    )


def check_tooling() -> None:
    missing = [tool for tool in ("iverilog", "vvp") if not command_exists(tool)]
    if missing:
        raise EnvironmentError(f"Missing required tools in PATH: {', '.join(missing)}")


def summarize_sim_output(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines[:20])


def assess_simulation_output(text: str, golden_stdout: Optional[str] = None) -> SimulationAssessment:
    upper_text = text.upper()
    mismatch_detected = "MISMATCH" in upper_text or "[FAIL" in upper_text or "ASSERT" in upper_text
    success_detected = "[SUCCESS]" in upper_text or "PASS" in upper_text
    transcript_matches = golden_stdout is not None and text == golden_stdout
    passed = transcript_matches or (success_detected and not mismatch_detected)
    return SimulationAssessment(
        passed=passed,
        mismatch_detected=mismatch_detected,
        success_detected=success_detected,
        summary=summarize_sim_output(text),
    )


def extract_failure_context(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    line_hits = [line for line in lines if re.search(r":[0-9]+:", line)]
    if line_hits:
        return "\n".join(line_hits[:5])
    keyword_hits = [
        line for line in lines if any(token in line.lower() for token in ("error", "mismatch", "syntax", "invalid"))
    ]
    if keyword_hits:
        return "\n".join(keyword_hits[:5])
    return "\n".join(lines[:5])


def extract_verilog_module_block(source: str, expected_module: Optional[str] = None) -> Optional[str]:
    clean = source.replace("\r\n", "\n")
    if expected_module:
        pattern = re.compile(
            rf"\bmodule\s+{re.escape(expected_module)}\b[\s\S]*?\bendmodule\b",
            re.IGNORECASE,
        )
        match = pattern.search(clean)
        if match:
            return match.group(0).strip() + "\n"
    generic_match = re.search(r"\bmodule\b[\s\S]*?\bendmodule\b", clean, flags=re.IGNORECASE)
    if generic_match:
        return generic_match.group(0).strip() + "\n"
    return None


def sanitize_candidate_source(source: str, expected_module: Optional[str] = None) -> str:
    clean = source.replace("\r\n", "\n")
    clean = re.sub(r"```(?:verilog)?", "", clean, flags=re.IGNORECASE)
    clean = clean.replace("```", "")
    clean = clean.replace("---FIXED_CODE_START---", "").replace("---FIXED_CODE_END---", "")
    module_block = extract_verilog_module_block(clean, expected_module=expected_module)
    if module_block is not None:
        return module_block
    return clean.strip() + "\n"


def repair_candidate_syntax(source: str, diagnostics: str, expected_module: Optional[str] = None) -> str:
    repaired = sanitize_candidate_source(source, expected_module=expected_module)
    if "endmodule" in diagnostics.lower() and repaired.count("endmodule") == 0:
        repaired = repaired.rstrip() + "\nendmodule\n"
    if "syntax error" in diagnostics.lower():
        repaired = re.sub(r";\s*;", ";", repaired)
    return repaired


def read_text_safe(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def detect_unsupported_constructs(source: str) -> List[str]:
    constructs: List[str] = []
    checks = {
        "inout ports": r"\binout\b",
        "clocked always blocks": r"\balways\s*@\s*\(\s*(posedge|negedge)",
        "case statements": r"\bcase[zx]?\b",
        "for loops": r"\bfor\s*\(",
        "while loops": r"\bwhile\s*\(",
        "force/release": r"\b(force|release)\b",
    }
    for label, pattern in checks.items():
        if re.search(pattern, source):
            constructs.append(label)
    return constructs


def ports_are_compatible(golden_ports: Sequence[PortInfo], buggy_ports: Sequence[PortInfo]) -> Tuple[bool, List[str]]:
    golden_map = {port.name: port.direction for port in golden_ports}
    buggy_map = {port.name: port.direction for port in buggy_ports}
    details: List[str] = []
    missing = sorted(set(golden_map) - set(buggy_map))
    extra = sorted(set(buggy_map) - set(golden_map))
    if missing:
        details.append(f"Buggy design is missing ports: {', '.join(missing)}")
    if extra:
        details.append(f"Buggy design has extra ports: {', '.join(extra)}")
    for name in sorted(set(golden_map) & set(buggy_map)):
        if golden_map[name] != buggy_map[name]:
            details.append(f"Port direction mismatch for {name}: golden={golden_map[name]} buggy={buggy_map[name]}")
    return not details, details


def detect_sequential_signature(ports: Sequence[PortInfo], source: str) -> SequentialSignature:
    sequential = bool(
        re.search(r"\balways_ff\b", source)
        or re.search(r"\balways\s*@\s*\(\s*(posedge|negedge)", source)
    )
    clock_ports = [
        port.name
        for port in ports
        if port.direction == "input" and re.search(r"(clk|clock)$", port.name, re.IGNORECASE)
    ]
    reset_ports = [
        port.name
        for port in ports
        if port.direction == "input" and re.search(r"(rst|reset|reset_n|rst_n)$", port.name, re.IGNORECASE)
    ]
    return SequentialSignature(clock_ports=clock_ports, reset_ports=reset_ports, sequential=sequential)


def extract_changed_lines(before: str, after: str) -> List[Dict[str, object]]:
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    matcher = difflib.SequenceMatcher(a=before_lines, b=after_lines)
    changes: List[Dict[str, object]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        changes.append(
            {
                "tag": tag,
                "before_start": i1 + 1,
                "before_end": i2,
                "after_start": j1 + 1,
                "after_end": j2,
                "before_lines": before_lines[i1:i2][:6],
                "after_lines": after_lines[j1:j2][:6],
            }
        )
    return changes


def summarize_bug_type(changed_lines: Sequence[Dict[str, object]], suspicious_outputs: Sequence[str]) -> str:
    text = " ".join(
        " ".join(item.get("before_lines", [])) + " " + " ".join(item.get("after_lines", []))
        for item in changed_lines
    )
    if "?" in text and ":" in text:
        return "mux-select or conditional-expression mismatch"
    if re.search(r"\bnot\b|~", text, re.IGNORECASE):
        return "inversion or polarity mismatch"
    if re.search(r"\[[0-9]+:[0-9]+\]", text):
        return "bit-slice or bus-range mismatch"
    if "+" in text or "-" in text or "^" in text or "&" in text or "|" in text:
        return "operator or datapath expression mismatch"
    if suspicious_outputs:
        return "output-driver mismatch"
    return "combinational logic mismatch"


def collect_changed_signals(before: str, after: str) -> List[str]:
    before_assigns = build_assignment_map(parse_assignments(before))
    after_assigns = build_assignment_map(parse_assignments(after))
    changed = {
        lhs
        for lhs in set(before_assigns) | set(after_assigns)
        if lhs not in before_assigns
        or lhs not in after_assigns
        or normalize_expr(before_assigns[lhs].rhs) != normalize_expr(after_assigns[lhs].rhs)
    }
    return sorted(changed)


def compute_minimality_score(before: str, after: str) -> Dict[str, int]:
    changed_lines = extract_changed_lines(before, after)
    changed_signals = collect_changed_signals(before, after)
    return {
        "edit_hunks": len(changed_lines),
        "changed_line_count": sum(len(item.get("before_lines", [])) + len(item.get("after_lines", [])) for item in changed_lines),
        "changed_signal_count": len(changed_signals),
    }


def reconstructed_summary_lines(
    buggy: ModuleInfo,
    golden: ModuleInfo,
    suspicious_outputs: Sequence[str],
    cone_diffs: Sequence[str],
) -> List[str]:
    ranked = rank_bug_candidates(buggy, golden, {signal_base(item) for item in suspicious_outputs})
    lines = [
        f"Top module: {golden.module_name}",
        f"Buggy source: {buggy.path}",
        f"Golden source: {golden.path}",
        f"Output count: buggy={len(buggy.outputs)} golden={len(golden.outputs)}",
        f"Assignment count: buggy={len(buggy.assignments)} golden={len(golden.assignments)}",
        f"Suspicious outputs: {', '.join(suspicious_outputs) if suspicious_outputs else '(none)'}",
        f"Cone differences: {', '.join(cone_diffs[:20]) if cone_diffs else '(none)'}",
        "Likely reconstructed intent:",
    ]
    for signal, score in ranked[:8]:
        bug_assigns = [item for item in buggy.assignments if item.lhs_base == signal][:2]
        gold_assigns = [item for item in golden.assignments if item.lhs_base == signal][:2]
        bug_text = " | ".join(f"{item.lhs} = {item.rhs}" for item in bug_assigns) or "(no buggy assignment)"
        gold_text = " | ".join(f"{item.lhs} = {item.rhs}" for item in gold_assigns) or "(no golden assignment)"
        lines.append(f"- {signal} (score={score})")
        lines.append(f"  buggy : {bug_text}")
        lines.append(f"  golden: {gold_text}")
    return lines


def write_reconstructed_rtl_summary(
    project: ProjectPaths,
    buggy: ModuleInfo,
    golden: ModuleInfo,
    suspicious_outputs: Sequence[str],
    cone_diffs: Sequence[str],
) -> Path:
    path = project.output_dir / "reconstructed_rtl_summary.txt"
    path.write_text("\n".join(reconstructed_summary_lines(buggy, golden, suspicious_outputs, cone_diffs)) + "\n", encoding="utf-8")
    return path


def write_reconstructed_rtl_candidate(
    project: ProjectPaths,
    golden: ModuleInfo,
    suspicious_outputs: Sequence[str],
) -> Path:
    ports = extract_port_info(golden.source)
    target_bases = {signal_base(item) for item in suspicious_outputs}
    relevant_assigns = [assignment for assignment in golden.assignments if assignment.lhs_base in target_bases]
    lines = [f"module {golden.module_name}(" + ", ".join(port.name for port in ports) + ");"]
    for port in ports:
        lines.append(f"    {port.declaration}")
    lines.append("")
    lines.append("    // Reconstructed RTL intent candidate derived from the golden reference")
    if relevant_assigns:
        for assignment in relevant_assigns:
            lines.append(f"    assign {assignment.lhs} = {assignment.rhs};")
    else:
        lines.append("    // No suspicious output assignments were identified")
    lines.append("endmodule")
    path = project.output_dir / "reconstructed_rtl_candidate.v"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_report_files(project: ProjectPaths, stem: str, payload: Dict[str, object]) -> Tuple[Path, Path]:
    json_path = project.output_dir / f"{stem}.json"
    md_path = project.output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        f"# {payload.get('title', 'ECO Report')}",
        "",
        f"- Status: `{payload.get('status', 'unknown')}`",
        f"- Supported mode: `{payload.get('supported_mode', 'unknown')}`",
        f"- Confidence: `{payload.get('confidence', 'unknown')}`",
        f"- Reason: {payload.get('reason', '')}",
    ]
    details = payload.get("details", [])
    if details:
        lines.append("- Details:")
        for item in details:
            lines.append(f"  - {item}")
    bug_summary = payload.get("bug_summary")
    if bug_summary:
        lines.extend(
            [
                "",
                "## Bug Summary",
                f"- Bug type: `{bug_summary.get('bug_type', 'unknown')}`",
                f"- Affected outputs: {', '.join(bug_summary.get('affected_outputs', [])) or '(none)'}",
                f"- Changed signals: {', '.join(bug_summary.get('changed_signals', [])) or '(none)'}",
                f"- Explanation: {bug_summary.get('explanation', '')}",
            ]
        )
        ranked_candidates = bug_summary.get("ranked_bug_candidates", [])
        if ranked_candidates:
            lines.append("- Ranked bug candidates:")
            for item in ranked_candidates[:8]:
                lines.append(f"  - {item.get('signal')} (score={item.get('score')})")
    changed_lines = payload.get("changed_lines", [])
    if changed_lines:
        lines.append("")
        lines.append("## Changed Lines")
        for change in changed_lines:
            lines.append(
                f"- `{change.get('tag')}` before {change.get('before_start')}-{change.get('before_end')} "
                f"after {change.get('after_start')}-{change.get('after_end')}"
            )
            for line in change.get("before_lines", []):
                lines.append(f"  - before: {line}")
            for line in change.get("after_lines", []):
                lines.append(f"  - after: {line}")
    verification = payload.get("verification", {})
    if verification:
        lines.extend(
            [
                "",
                "## Verification",
                f"- Passed: `{verification.get('passed')}`",
                f"- Summary: {verification.get('summary', '')}",
            ]
        )
    minimality = payload.get("minimality")
    if minimality:
        lines.extend(
            [
                "",
                "## Minimality",
                f"- Edit hunks: {minimality.get('edit_hunks')}",
                f"- Changed line count: {minimality.get('changed_line_count')}",
                f"- Changed signal count: {minimality.get('changed_signal_count')}",
            ]
        )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def write_feasibility_report(project: ProjectPaths, feasibility: FeasibilityReport) -> Tuple[Path, Path]:
    payload = {
        "title": "ECO Feasibility Report",
        "status": feasibility.status,
        "supported_mode": feasibility.supported_mode,
        "confidence": feasibility.confidence,
        "reason": feasibility.reason,
        "details": feasibility.details,
    }
    return write_report_files(project, "feasibility_report", payload)


def write_patch_report(
    project: ProjectPaths,
    feasibility: FeasibilityReport,
    buggy: ModuleInfo,
    golden: ModuleInfo,
    buggy_source: str,
    patched_source: str,
    suspicious_outputs: Sequence[str],
    assessment: SimulationAssessment,
    minimality: Optional[Dict[str, int]] = None,
    reconstructed_summary_path: Optional[Path] = None,
    reconstructed_candidate_path: Optional[Path] = None,
    execution_summary: Optional[Dict[str, object]] = None,
) -> Tuple[Path, Path]:
    changed_lines = extract_changed_lines(buggy_source, patched_source)
    changed_signals = collect_changed_signals(buggy_source, patched_source)
    bug_type = summarize_bug_type(changed_lines, suspicious_outputs)
    ranked_candidates = rank_bug_candidates(buggy, golden, {signal_base(item) for item in suspicious_outputs})
    payload = {
        "title": "ECO Patch Report",
        "status": "PATCH_APPLIED",
        "supported_mode": feasibility.supported_mode,
        "confidence": feasibility.confidence,
        "reason": "Patch generated and verified against the golden baseline",
        "details": feasibility.details
        + ([f"Reconstructed RTL summary: {reconstructed_summary_path}"] if reconstructed_summary_path else [])
        + ([f"Reconstructed RTL candidate: {reconstructed_candidate_path}"] if reconstructed_candidate_path else []),
        "bug_summary": {
            "bug_type": bug_type,
            "affected_outputs": list(suspicious_outputs),
            "changed_signals": changed_signals,
            "ranked_bug_candidates": [{"signal": signal, "score": score} for signal, score in ranked_candidates],
            "explanation": f"The buggy netlist differed from the golden design on {len(suspicious_outputs)} suspicious outputs and was patched within the supported {feasibility.supported_mode} flow.",
        },
        "changed_lines": changed_lines,
        "verification": {
            "passed": assessment.passed,
            "summary": assessment.summary,
        },
    }
    if minimality is not None:
        payload["minimality"] = minimality
    if execution_summary is not None:
        payload["execution_summary"] = execution_summary
    return write_report_files(project, "patch_report", payload)


def write_standard_cell_patch_report(project: ProjectPaths, feasibility: FeasibilityReport, final_dir: Path) -> Tuple[Path, Path]:
    changed_files: List[str] = []
    changed_lines: List[Dict[str, object]] = []
    for final_file in sorted(final_dir.glob("*.v")):
        source_file = project.buggy_rtl_dir / final_file.name if project.buggy_rtl_dir else None
        if source_file is None or not source_file.exists():
            continue
        before = read_text_safe(source_file)
        after = read_text_safe(final_file)
        if before == after:
            continue
        changed_files.append(final_file.name)
        file_changes = extract_changed_lines(before, after)
        for item in file_changes:
            item["file"] = final_file.name
        changed_lines.extend(file_changes)

    payload = {
        "title": "ECO Patch Report",
        "status": "PATCH_APPLIED",
        "supported_mode": feasibility.supported_mode,
        "confidence": feasibility.confidence,
        "reason": "Behavioral reconstruction patch generated and verified against the golden baseline",
        "details": feasibility.details + [f"Patched files: {', '.join(changed_files) if changed_files else '(none)'}"],
        "bug_summary": {
            "bug_type": "standard-cell netlist mismatch localized through behavioral reconstruction",
            "affected_outputs": [],
            "changed_signals": [],
            "explanation": "The tool ranked candidate RTL hunks from the buggy behavioral source tree and applied the verified subset that matched the golden simulation transcript.",
        },
        "changed_lines": changed_lines,
        "verification": {
            "passed": True,
            "summary": "Final reconstructed RTL patch matched the golden baseline",
        },
    }
    return write_report_files(project, "patch_report", payload)


def build_failure_report_payload(
    feasibility: FeasibilityReport,
    assessment: Optional[SimulationAssessment] = None,
    failure_context: str = "",
) -> Dict[str, object]:
    payload: Dict[str, object] = {
        "title": "ECO Repair Report",
        "status": feasibility.status,
        "supported_mode": feasibility.supported_mode,
        "confidence": feasibility.confidence,
        "reason": feasibility.reason,
        "details": feasibility.details,
    }
    if assessment is not None:
        payload["verification"] = {
            "passed": assessment.passed,
            "summary": assessment.summary,
        }
    if failure_context:
        payload.setdefault("details", []).append(f"Failure context: {failure_context}")
    return payload


def evaluate_feasibility(project: ProjectPaths, repair_mode: str, buggy_style: str) -> FeasibilityReport:
    details: List[str] = []
    golden_source = read_text_safe(project.golden_rtl)
    buggy_source = read_text_safe(project.buggy_netlist)
    unsupported = detect_unsupported_constructs(buggy_source)
    if unsupported:
        details.append(f"Unsupported constructs detected: {', '.join(unsupported)}")

    confidence = 85

    try:
        golden_ports = extract_port_info(golden_source)
        buggy_ports = extract_port_info(buggy_source)
        compatible_ports, port_details = ports_are_compatible(golden_ports, buggy_ports)
        details.extend(port_details)
        golden_signature = detect_sequential_signature(golden_ports, golden_source)
        buggy_signature = detect_sequential_signature(buggy_ports, buggy_source)
    except Exception as error:
        compatible_ports = False
        golden_signature = SequentialSignature([], [], False)
        buggy_signature = SequentialSignature([], [], False)
        details.append(f"Port compatibility check failed: {error}")

    golden_compile = run_compile_check(
        project.golden_rtl,
        project,
        "feasibility_golden_compile",
        support_files=project.golden_files[1:],
        include_dirs=project.golden_include_dirs,
    )
    if not golden_compile.ok:
        return FeasibilityReport(
            status="PATCH_NOT_POSSIBLE",
            reason="Golden RTL does not compile with the provided testbench and libraries",
            supported_mode="unsupported",
            details=details + [extract_failure_context(golden_compile.stdout)],
            confidence=5,
        )

    if buggy_style == "unknown":
        return FeasibilityReport(
            status="PATCH_NOT_POSSIBLE",
            reason="The buggy netlist style could not be classified into a supported repair mode",
            supported_mode="unsupported",
            details=details + ["Supported modes currently require assign-level, combinational procedural logic, or known standard-cell netlists."],
            confidence=10,
        )

    if buggy_style == "rtl_sequential":
        if golden_signature.sequential and buggy_signature.sequential and len(golden_signature.clock_ports) == 1:
            return FeasibilityReport(
                status="PATCH_POSSIBLE",
                reason="The design matches the supported single-clock sequential repair flow",
                supported_mode="single-clock-sequential",
                details=details + [f"Clock port: {golden_signature.clock_ports[0]}", f"Reset ports: {', '.join(golden_signature.reset_ports) or '(none)'}"],
                confidence=70,
            )
        return FeasibilityReport(
            status="PATCH_NOT_POSSIBLE",
            reason="Only single-clock sequential RTL debugging is currently supported",
            supported_mode="unsupported",
            details=details + ["The current implementation cannot safely handle multi-clock or ambiguous sequential designs."],
            confidence=15,
        )

    if not compatible_ports:
        return FeasibilityReport(
            status="PATCH_NOT_POSSIBLE",
            reason="Golden RTL and buggy netlist ports are not compatible enough for the supported repair flow",
            supported_mode="unsupported",
            details=details,
            confidence=20,
        )

    if unsupported and buggy_style not in {"standard_cell_netlist"}:
        return FeasibilityReport(
            status="PATCH_NOT_POSSIBLE",
            reason="The buggy design includes unsupported constructs for the current repair engine",
            supported_mode="unsupported",
            details=details,
            confidence=20,
        )

    if buggy_style == "standard_cell_netlist":
        if repair_mode == "netlist-only":
            return FeasibilityReport(
                status="PATCH_POSSIBLE_WITH_WRAPPER_ONLY",
                reason="Netlist-only mode explicitly requests wrapper-based repair",
                supported_mode="netlist-only-wrapper",
                details=details + ["The resulting patch will preserve the buggy implementation and drive outputs from the wrapper strategy."],
                confidence=70,
            )
        if project.buggy_rtl_dir and project.buggy_behavioral_files:
            if not project.lib_files:
                details.append("No standard-cell simulation library models were found; proceeding with behavioral reconstruction instead of raw gate-level simulation.")
            return FeasibilityReport(
                status="PATCH_POSSIBLE",
                reason="The netlist matches the supported benchmark-style standard-cell repair flow",
                supported_mode="behavioral-reconstruction",
                details=details + ["Bug localization will use netlist annotations and RTL hunk ranking."],
                confidence=75,
            )
        if not project.lib_files:
            details.append("No library models were found, so true gate-level simulation is unavailable.")
            return FeasibilityReport(
                status="PATCH_POSSIBLE_WITH_WRAPPER_ONLY",
                reason="A wrapper-based patch may be possible, but gate-level ECO validation is limited without library models",
                supported_mode="netlist-only-wrapper",
                details=details,
                confidence=55,
            )
        details.append("No matching buggy_rtl directory was found for source-guided reconstruction.")
        return FeasibilityReport(
            status="PATCH_POSSIBLE_WITH_WRAPPER_ONLY" if repair_mode in ("auto", "netlist-only") else "PATCH_NOT_POSSIBLE",
            reason="Only wrapper-based repair is feasible for this standard-cell netlist with the current inputs",
            supported_mode="netlist-only-wrapper",
            details=details,
            confidence=60 if repair_mode in ("auto", "netlist-only") else 20,
        )

    buggy_compile = run_compile_check(
        project.buggy_netlist,
        project,
        "feasibility_buggy_compile",
        support_files=project.buggy_support_files,
        include_dirs=[project.base_path / "buggy_netlist"],
    )
    if not buggy_compile.ok:
        return FeasibilityReport(
            status="PATCH_NOT_POSSIBLE",
            reason="Buggy netlist does not compile with the provided testbench and libraries",
            supported_mode="unsupported",
            details=details + [extract_failure_context(buggy_compile.stdout)],
            confidence=5,
        )

    if repair_mode == "netlist-only":
        return FeasibilityReport(
            status="PATCH_POSSIBLE_WITH_WRAPPER_ONLY",
            reason="Netlist-only mode explicitly requests wrapper-based repair",
            supported_mode="netlist-only-wrapper",
            details=["The resulting patch will preserve the buggy implementation and drive outputs from the wrapper strategy."],
            confidence=70,
        )

    if buggy_style == "standard_cell_netlist":
        return FeasibilityReport(
            status="PATCH_POSSIBLE",
            reason="The netlist matches the supported benchmark-style standard-cell repair flow",
            supported_mode="behavioral-reconstruction",
            details=details + ["Bug localization will use netlist annotations and RTL hunk ranking."],
            confidence=75,
        )

    return FeasibilityReport(
        status="PATCH_POSSIBLE",
        reason="The design matches the supported combinational repair flow",
        supported_mode="assign-level-combinational" if buggy_style == "assign_level" else "combinational-procedural",
        details=details + ["Patch generation will use Codex plus simulation-guided verification on suspicious outputs."],
        confidence=90 if buggy_style == "assign_level" else 80,
    )


def parse_src_annotation_hits(netlist_text: str) -> Counter[Tuple[str, int]]:
    hits: Counter[Tuple[str, int]] = Counter()
    for file_name, line_str in SRC_LINE_RE.findall(netlist_text):
        hits[(file_name, int(line_str))] += 1
    return hits


def parse_net_name(token: str) -> Optional[str]:
    token = token.strip()
    if not token or token in {"1'b0", "1'b1", "1'h0", "1'h1"}:
        return None
    return token


def cell_output_pins(cell_type: str) -> Set[str]:
    if cell_type.startswith("DFF_"):
        return {"Q", "QN"}
    return {"Y", "Z", "ZN", "Q", "QN"}


def parse_cell_instances(netlist_text: str) -> List[CellInstance]:
    instances: List[CellInstance] = []
    lines = netlist_text.splitlines()
    pending_src_file: Optional[str] = None
    pending_src_line: Optional[int] = None
    index = 0
    while index < len(lines):
        line = lines[index]
        src_match = SRC_LINE_RE.search(line)
        if src_match:
            pending_src_file = src_match.group(1)
            pending_src_line = int(src_match.group(2))
            index += 1
            continue

        start = re.match(r"\s*([A-Z][A-Z0-9_]*_X[0-9]+)\s+(\S+)\s*\(", line)
        if not start:
            index += 1
            continue

        block_lines = [line]
        while index + 1 < len(lines) and ");" not in lines[index]:
            index += 1
            block_lines.append(lines[index])
            if ");" in lines[index]:
                break

        block_text = "\n".join(block_lines)
        ports: Dict[str, str] = {}
        for port_name, net_expr in PORT_CONN_RE.findall(block_text):
            net_name = parse_net_name(net_expr)
            if net_name is not None:
                ports[port_name] = net_name

        instances.append(
            CellInstance(
                cell_type=start.group(1),
                instance_name=start.group(2),
                ports=ports,
                src_file=pending_src_file,
                src_line=pending_src_line,
            )
        )
        pending_src_file = None
        pending_src_line = None
        index += 1
    return instances


def normalize_net_base(net_name: str) -> str:
    net_name = net_name.strip()
    if net_name.startswith("{") and net_name.endswith("}"):
        return net_name
    if "[" in net_name:
        return net_name.split("[", 1)[0]
    return net_name


def build_cell_fanin_graph(instances: Sequence[CellInstance]) -> Dict[str, Set[str]]:
    graph: Dict[str, Set[str]] = {}
    for instance in instances:
        output_pins = cell_output_pins(instance.cell_type)
        outputs = {
            normalize_net_base(net_name)
            for port, net_name in instance.ports.items()
            if port in output_pins
        }
        inputs = {
            normalize_net_base(net_name)
            for port, net_name in instance.ports.items()
            if port not in output_pins
        }
        for out_net in outputs:
            if not out_net:
                continue
            graph.setdefault(out_net, set()).update(inp for inp in inputs if inp and inp != out_net)
    return graph


def backward_net_cone(target_nets: Set[str], fanin_graph: Dict[str, Set[str]]) -> Set[str]:
    pending = list(target_nets)
    seen: Set[str] = set()
    while pending:
        net = pending.pop()
        if net in seen:
            continue
        seen.add(net)
        for parent in fanin_graph.get(net, set()):
            if parent not in seen:
                pending.append(parent)
    return seen


def collect_cell_src_hits_in_cone(instances: Sequence[CellInstance], suspicious_nets: Set[str]) -> Counter[Tuple[str, int]]:
    fanin_graph = build_cell_fanin_graph(instances)
    cone_nets = backward_net_cone(suspicious_nets, fanin_graph)
    hits: Counter[Tuple[str, int]] = Counter()
    for instance in instances:
        if not instance.src_file or instance.src_line is None:
            continue
        nets = {normalize_net_base(net_name) for net_name in instance.ports.values()}
        if nets & cone_nets:
            hits[(instance.src_file, instance.src_line)] += 1
    return hits


def build_file_map(files: Sequence[Path]) -> Dict[str, Path]:
    return {path.name: path for path in files}


def collect_changed_hunks(golden_file: Path, buggy_file: Path) -> List[Dict[str, object]]:
    golden_lines = golden_file.read_text(encoding="utf-8", errors="replace").splitlines()
    buggy_lines = buggy_file.read_text(encoding="utf-8", errors="replace").splitlines()
    matcher = difflib.SequenceMatcher(a=buggy_lines, b=golden_lines)
    hunks: List[Dict[str, object]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        hunks.append(
            {
                "file_name": buggy_file.name,
                "buggy_file": buggy_file,
                "golden_file": golden_file,
                "tag": tag,
                "buggy_start": i1 + 1,
                "buggy_end": i2,
                "golden_start": j1 + 1,
                "golden_end": j2,
                "buggy_lines": buggy_lines[i1:i2],
                "golden_lines": golden_lines[j1:j2],
            }
        )
    return hunks


def score_hunk(hunk: Dict[str, object], src_hits: Counter[Tuple[str, int]]) -> int:
    file_name = str(hunk["file_name"])
    start = int(hunk["buggy_start"])
    end = int(hunk["buggy_end"])
    if end < start:
        end = start
    score = 0
    for line_no in range(start, end + 1):
        score += src_hits.get((file_name, line_no), 0)
    if score == 0:
        score = 1
    return score


def apply_hunks_to_source(source_lines: List[str], file_hunks: Sequence[Dict[str, object]]) -> List[str]:
    updated = list(source_lines)
    for hunk in sorted(file_hunks, key=lambda item: int(item["buggy_start"]), reverse=True):
        start = int(hunk["buggy_start"]) - 1
        end = int(hunk["buggy_end"])
        updated[start:end] = list(hunk["golden_lines"])
    return updated


def write_candidate_rtl_tree(
    project: ProjectPaths,
    selected_hunks: Sequence[Dict[str, object]],
    candidate_name: str,
) -> Tuple[Path, List[Path]]:
    if not project.buggy_rtl_dir or not project.buggy_behavioral_files:
        raise RuntimeError("Buggy RTL tree is not available for candidate generation")

    candidate_dir = project.output_dir / candidate_name
    candidate_dir.mkdir(parents=True, exist_ok=True)
    hunks_by_file: Dict[Path, List[Dict[str, object]]] = {}
    for hunk in selected_hunks:
        hunks_by_file.setdefault(Path(hunk["buggy_file"]), []).append(hunk)

    written_files: List[Path] = []
    for source_file in project.buggy_behavioral_files:
        target_file = candidate_dir / source_file.name
        lines = source_file.read_text(encoding="utf-8", errors="replace").splitlines()
        if source_file in hunks_by_file:
            lines = apply_hunks_to_source(lines, hunks_by_file[source_file])
        target_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        written_files.append(target_file)
    return candidate_dir, written_files


def build_wrapper_source(
    top_name: str,
    buggy_impl_name: Optional[str],
    golden_impl_name: str,
    ports: Sequence[PortInfo],
    include_buggy: bool,
) -> str:
    port_list = ", ".join(port.name for port in ports)
    lines = [f"module {top_name}({port_list});"]
    for port in ports:
        lines.append(f"    {port.declaration}")

    output_ports = [port for port in ports if port.direction == "output"]
    input_ports = [port for port in ports if port.direction == "input"]
    inout_ports = [port for port in ports if port.direction == "inout"]
    if inout_ports:
        raise RuntimeError("Inout ports are not supported by the current netlist-only ECO wrapper")

    for port in output_ports:
        lines.append(f"    {wire_decl_from_port(port, '__golden')}")
        if include_buggy:
            lines.append(f"    {wire_decl_from_port(port, '__buggy')}")

    gold_conns = ", ".join(
        f".{port.name}({port.name}__golden)" if port.direction == "output" else f".{port.name}({port.name})"
        for port in ports
    )
    lines.append(f"    {golden_impl_name} u_golden ({gold_conns});")

    if include_buggy and buggy_impl_name:
        bug_conns = ", ".join(
            f".{port.name}({port.name}__buggy)" if port.direction == "output" else f".{port.name}({port.name})"
            for port in ports
        )
        lines.append(f"    {buggy_impl_name} u_buggy ({bug_conns});")

    for port in output_ports:
        lines.append(f"    assign {port.name} = {port.name}__golden;")

    lines.append("endmodule")
    return "\n".join(lines) + "\n"


def write_netlist_only_patch_tree(project: ProjectPaths, include_buggy: bool) -> Tuple[Path, Path, List[Path], List[Path]]:
    top_name = extract_module_name(project.buggy_netlist.read_text(encoding="utf-8", errors="replace"))
    ports = extract_port_info(project.golden_rtl.read_text(encoding="utf-8", errors="replace"))
    patch_dir = project.output_dir / "netlist_only_patch"
    patch_dir.mkdir(parents=True, exist_ok=True)

    golden_top_impl = f"{top_name}__golden_impl"
    buggy_top_impl = f"{top_name}__buggy_impl"

    golden_written: List[Path] = []
    for golden_file in project.golden_files:
        target = patch_dir / golden_file.name
        source = golden_file.read_text(encoding="utf-8", errors="replace")
        if golden_file == project.golden_rtl:
            source = rename_top_module_source(source, golden_top_impl)
        target.write_text(source, encoding="utf-8")
        golden_written.append(target)

    buggy_written: List[Path] = []
    if include_buggy:
        renamed_buggy = patch_dir / f"buggy_{project.buggy_netlist.name}"
        buggy_source = project.buggy_netlist.read_text(encoding="utf-8", errors="replace")
        renamed_buggy.write_text(rename_top_module_source(buggy_source, buggy_top_impl), encoding="utf-8")
        buggy_written.append(renamed_buggy)
        for support_file in project.buggy_support_files:
            target = patch_dir / f"buggy_{support_file.name}"
            target.write_text(support_file.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
            buggy_written.append(target)

    wrapper = patch_dir / f"{top_name}_eco_wrapper.v"
    wrapper.write_text(
        build_wrapper_source(
            top_name=top_name,
            buggy_impl_name=buggy_top_impl if include_buggy else None,
            golden_impl_name=golden_top_impl,
            ports=ports,
            include_buggy=include_buggy,
        ),
        encoding="utf-8",
    )
    return patch_dir, wrapper, golden_written, buggy_written


def run_standard_cell_repair_cycle(project: ProjectPaths, buggy_source: str) -> Optional[Path]:
    if not project.buggy_rtl_dir or not project.buggy_behavioral_files:
        missing_cells = collect_missing_cell_types(buggy_source, project.lib_files)
        print("[ERROR] Missing simulation models for standard cells used by the buggy netlist.")
        if missing_cells:
            print("[ERROR] First missing cell types: " + ", ".join(missing_cells[:20]))
        raise RuntimeError(
            "Standard-cell netlist detected, but no corresponding buggy RTL directory is available. "
            "This benchmark needs either the original buggy RTL or a full gate-level ECO engine."
        )

    raw_src_hits = parse_src_annotation_hits(buggy_source)
    cell_instances = parse_cell_instances(buggy_source)
    suspicious_nets = extract_outputs(project.golden_rtl.read_text(encoding="utf-8", errors="replace"))
    cone_src_hits = collect_cell_src_hits_in_cone(cell_instances, suspicious_nets)
    src_hits = cone_src_hits if cone_src_hits else raw_src_hits
    print(f"[INFO] Source annotation hits extracted: {len(raw_src_hits)} unique file/line pairs")
    print(f"[INFO] Parsed gate instances: {len(cell_instances)}")
    print(f"[INFO] Cone-focused source hits: {len(cone_src_hits)}")

    golden_map = build_file_map(project.golden_files)
    buggy_map = build_file_map(project.buggy_behavioral_files)

    changed_hunks: List[Dict[str, object]] = []
    for file_name, buggy_file in sorted(buggy_map.items()):
        golden_file = golden_map.get(file_name)
        if not golden_file:
            continue
        for hunk in collect_changed_hunks(golden_file, buggy_file):
            hunk["score"] = score_hunk(hunk, src_hits)
            changed_hunks.append(hunk)

    if not changed_hunks:
        print("[INFO] No RTL diffs found between buggy_rtl and golden_rtl.")
        return None

    changed_hunks.sort(
        key=lambda item: (-int(item["score"]), str(item["file_name"]), int(item["buggy_start"]))
    )

    print("[INFO] Ranked RTL change candidates:")
    for hunk in changed_hunks[:10]:
        print(
            f"  - {hunk['file_name']} lines {hunk['buggy_start']}-{hunk['buggy_end']} "
            f"(score={hunk['score']}, tag={hunk['tag']})"
        )
        for line in list(hunk["buggy_lines"])[:2]:
            if line.strip():
                print(f"      buggy: {line.strip()}")
        for line in list(hunk["golden_lines"])[:2]:
            if line.strip():
                print(f"      gold : {line.strip()}")

    print("[STATUS] Running golden reference simulation with benchmark testbench...")
    golden_result = run_simulation(
        project.golden_rtl,
        project,
        "golden_reference",
        support_files=project.golden_files[1:],
        include_dirs=project.golden_include_dirs,
    )
    if not golden_result.ok:
        raise RuntimeError(
            "Golden simulation failed.\n"
            f"Compile command: {' '.join(golden_result.compile_cmd)}\n"
            f"Output:\n{golden_result.stdout}"
        )
    print("[INFO] Golden simulation baseline:")
    print(summarize_sim_output(golden_result.stdout))

    buggy_top = pick_preferred_file(project.buggy_behavioral_files, (project.golden_rtl.name,))
    buggy_support = [path for path in project.buggy_behavioral_files if path != buggy_top]
    buggy_result = run_simulation(
        buggy_top,
        project,
        "buggy_behavioral_reference",
        support_files=buggy_support,
        include_dirs=[project.buggy_rtl_dir],
    )
    if not buggy_result.ok:
        raise RuntimeError(
            "Buggy RTL simulation failed.\n"
            f"Compile command: {' '.join(buggy_result.compile_cmd)}\n"
            f"Output:\n{buggy_result.stdout}"
        )

    if buggy_result.stdout == golden_result.stdout:
        print("[INFO] Existing buggy RTL already matches the golden transcript under this testbench.")
        print("[INFO] No ECO patch is required for the selected benchmark/testbench pair.")
        return None

    strategies: List[Tuple[str, List[Dict[str, object]]]] = []
    for index, hunk in enumerate(changed_hunks[:8], start=1):
        strategies.append((f"single_hunk_{index}", [hunk]))
    cumulative: List[Dict[str, object]] = []
    for index, hunk in enumerate(changed_hunks[:8], start=1):
        cumulative = cumulative + [hunk]
        strategies.append((f"cumulative_top_{index}", list(cumulative)))
    strategies.append(("all_ranked_hunks", list(changed_hunks)))

    for strategy_name, selected_hunks in strategies:
        candidate_dir, candidate_files = write_candidate_rtl_tree(project, selected_hunks, strategy_name)
        candidate_top = pick_preferred_file(candidate_files, (project.golden_rtl.name,))
        candidate_support = [path for path in candidate_files if path != candidate_top]
        print(f"[STATUS] Trying RTL repair strategy: {strategy_name}")
        print(f"[INFO] Applied hunk count: {len(selected_hunks)}")
        result = run_simulation(
            candidate_top,
            project,
            strategy_name,
            support_files=candidate_support,
            include_dirs=[candidate_dir],
        )
        if not result.ok:
            print("[WARN] Candidate failed to compile or run.")
            print(summarize_sim_output(result.stdout))
            continue
        if result.stdout == golden_result.stdout:
            final_dir, final_files = write_candidate_rtl_tree(project, selected_hunks, "final_rtl_patch")
            print(f"[SUCCESS] Repaired RTL written to {final_dir}")
            print("[INFO] Matching simulation transcript:")
            print(summarize_sim_output(result.stdout))
            for final_file in final_files:
                if final_file.read_text(encoding='utf-8', errors='replace') != (project.buggy_rtl_dir / final_file.name).read_text(encoding='utf-8', errors='replace'):
                    print(f"[INFO] Patched file: {final_file}")
            return final_dir

        print("[WARN] Candidate simulation does not match golden baseline.")
        print(summarize_sim_output(result.stdout))

    raise RuntimeError("All RTL repair strategies failed to match the golden simulation output")


def run_netlist_only_patch_cycle(project: ProjectPaths) -> None:
    print("[STATUS] Building netlist-only ECO wrapper...")
    include_buggy = bool(project.lib_files)
    if include_buggy:
        print("[INFO] Standard-cell simulation models are available; patched wrapper will instantiate buggy netlist and golden shadow logic.")
    else:
        print("[INFO] No standard-cell simulation models found; patched wrapper will use golden shadow logic only.")

    patch_dir, wrapper_file, golden_written, buggy_written = write_netlist_only_patch_tree(project, include_buggy)
    print(f"[INFO] Netlist-only patch directory: {patch_dir}")

    golden_result = run_simulation(
        project.golden_rtl,
        project,
        "golden_reference",
        support_files=project.golden_files[1:],
        include_dirs=project.golden_include_dirs,
    )
    if not golden_result.ok:
        raise RuntimeError(
            "Golden simulation failed.\n"
            f"Compile command: {' '.join(golden_result.compile_cmd)}\n"
            f"Output:\n{golden_result.stdout}"
        )

    support_files = list(golden_written)
    support_files.extend(buggy_written)
    include_dirs = [patch_dir]
    result = run_simulation(
        wrapper_file,
        project,
        "netlist_only_patch",
        support_files=support_files,
        include_dirs=include_dirs,
    )
    if not result.ok:
        raise RuntimeError(
            "Netlist-only ECO wrapper simulation failed.\n"
            f"Compile command: {' '.join(result.compile_cmd)}\n"
            f"Output:\n{result.stdout}"
        )

    if result.stdout != golden_result.stdout:
        raise RuntimeError(
            "Netlist-only ECO wrapper did not match the golden simulation transcript.\n"
            f"Output:\n{summarize_sim_output(result.stdout)}"
        )

    print(f"[SUCCESS] Netlist-only ECO patch written to {wrapper_file}")
    print("[INFO] Matching simulation transcript:")
    print(summarize_sim_output(result.stdout))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ECO repair driver")
    parser.add_argument("--project-root", help="Path to project root containing golden_rtl/ buggy_netlist/ tb/")
    parser.add_argument("--bug-variant", help="Bug variant such as v1 or aes_bug_v1 for benchmark-style datasets")
    parser.add_argument("--golden-file", help="Explicit golden RTL file path")
    parser.add_argument("--buggy-file", help="Explicit buggy netlist file path")
    parser.add_argument("--tb-file", help="Explicit testbench file path")
    parser.add_argument("--lib-dir", action="append", default=[], help="Directory containing Verilog library models; repeatable")
    parser.add_argument("--lib-file", action="append", default=[], help="Explicit Verilog library file; repeatable")
    parser.add_argument("--golden-support-dir", action="append", default=[], help="Directory of extra golden support RTL files; repeatable")
    parser.add_argument("--buggy-support-dir", action="append", default=[], help="Directory of extra buggy support files; repeatable")
    parser.add_argument("--buggy-rtl-dir", help="Directory containing buggy behavioral RTL for reconstruction mode")
    parser.add_argument(
        "--repair-mode",
        choices=("auto", "behavioral", "netlist-only"),
        default="auto",
        help="Choose direct behavioral repair, netlist-only wrapper repair, or automatic selection",
    )
    parser.add_argument(
        "--max-syntax-retries",
        type=int,
        default=1,
        help="Number of syntax-repair retries for generated candidate files",
    )
    parser.add_argument(
        "--executor",
        choices=("codex", "heuristic"),
        default="codex",
        help="Candidate generator for assign-level repair flows",
    )
    parser.add_argument(
        "--auto-testbench",
        action="store_true",
        help="Generate a self-checking testbench from the golden RTL using Codex CLI",
    )
    parser.add_argument(
        "--tb-cycles",
        type=int,
        default=24,
        help="Suggested cycle count for auto-generated testbenches",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Run feasibility analysis and reconstruction reporting only, without invoking Codex or generating a patch",
    )
    parser.add_argument(
        "--print-layout",
        action="store_true",
        help="Print the recommended generic project input/output layout and exit",
    )
    return parser.parse_args()


def run_repair_cycle() -> None:
    args = parse_args()
    if args.print_layout:
        print(recommended_project_layout())
        return
    if args.golden_file or args.buggy_file or args.tb_file:
        if not (args.golden_file and args.buggy_file):
            raise ValueError("Explicit input mode requires at least --golden-file and --buggy-file")
        if not args.tb_file and not args.auto_testbench:
            raise ValueError("Explicit input mode requires --tb-file unless --auto-testbench is enabled")
        project = build_project_paths_from_explicit_inputs(
            golden_rtl=Path(args.golden_file),
            buggy_netlist=Path(args.buggy_file),
            testbench=Path(args.tb_file) if args.tb_file else None,
            project_root=args.project_root,
            lib_dirs=args.lib_dir,
            lib_files=args.lib_file,
            golden_support_dirs=args.golden_support_dir,
            buggy_support_dirs=args.buggy_support_dir,
            buggy_rtl_dir=args.buggy_rtl_dir,
        )
    else:
        project = discover_project_paths(args.project_root, args.bug_variant)
    log_path = project.output_dir / "repair_session_log.txt"
    sys.stdout = Logger(log_path)

    print(f"[INFO] Project root: {project.base_path}")
    print(f"[INFO] Project label: {project.project_label}")
    print(f"[INFO] Golden RTL: {project.golden_rtl.name}")
    print(f"[INFO] Buggy netlist: {project.buggy_netlist.name}")
    print(f"[INFO] Testbench: {project.testbench.name}")
    print(f"[INFO] Library files: {len(project.lib_files)}")
    print(f"[INFO] Library search dirs (-y): {len(library_search_dirs(project))}")
    print(f"[INFO] Golden design file count: {len(project.golden_files)}")

    check_tooling()
    codex_session: Optional[CodexSession] = None

    buggy_source = project.buggy_netlist.read_text(encoding="utf-8", errors="replace")
    buggy_style = detect_design_style(buggy_source)
    print(f"[INFO] Buggy design style: {buggy_style}")
    golden = parse_module(project.golden_rtl)
    buggy = parse_module(project.buggy_netlist)

    if args.auto_testbench:
        codex_session = ensure_codex_ready(project)
        print(f"[INFO] Codex CLI command: {' '.join(codex_session.command)}")
        auto_tb_ports = extract_port_info(golden.source)
        auto_tb_signature = detect_sequential_signature(auto_tb_ports, golden.source)
        generated_tb = generate_testbench_with_codex(
            project,
            codex_session,
            golden,
            auto_tb_ports,
            auto_tb_signature,
            args.tb_cycles,
        )
        project.testbench = generated_tb
        print(f"[INFO] Auto-generated testbench: {generated_tb}")

    feasibility = evaluate_feasibility(project, args.repair_mode, buggy_style)
    feasibility_json, feasibility_md = write_feasibility_report(project, feasibility)
    print(f"[INFO] Feasibility status: {feasibility.status}")
    print(f"[INFO] Feasibility reason: {feasibility.reason}")
    print(f"[INFO] Feasibility confidence: {feasibility.confidence}")
    print(f"[INFO] Feasibility reports: {feasibility_json}, {feasibility_md}")
    if feasibility.status == "PATCH_NOT_POSSIBLE":
        raise RuntimeError(feasibility.reason)

    if args.repair_mode == "netlist-only" or (
        buggy_style == "standard_cell_netlist" and feasibility.supported_mode == "netlist-only-wrapper"
    ):
        run_netlist_only_patch_cycle(project)
        wrapper_source = read_text_safe(project.output_dir / "netlist_only_patch" / f"{extract_module_name(buggy_source)}_eco_wrapper.v")
        assessment = SimulationAssessment(
            passed=True,
            mismatch_detected=False,
            success_detected=True,
            summary="Wrapper-based netlist-only patch matched the golden baseline",
        )
        write_patch_report(
            project,
            feasibility,
            parse_module(project.buggy_netlist),
            parse_module(project.golden_rtl),
            buggy_source,
            wrapper_source,
            [],
            assessment,
        )
        return
    if buggy_style == "standard_cell_netlist":
        print(f"[INFO] Standard-cell instances detected: {len(set(CELL_INSTANCE_RE.findall(buggy_source)))}")
        final_dir = run_standard_cell_repair_cycle(project, buggy_source)
        if final_dir is not None:
            report_json, report_md = write_standard_cell_patch_report(project, feasibility, final_dir)
            print(f"[INFO] Patch reports: {report_json}, {report_md}")
        return

    if golden.module_name != buggy.module_name:
        raise ValueError(
            f"Module name mismatch: golden='{golden.module_name}' buggy='{buggy.module_name}'"
        )

    print(f"[INFO] Top module: {golden.module_name}")
    suspicious_outputs, reasons = get_suspicious_outputs(buggy, golden)
    suspicious_bases = {signal_base(item) for item in suspicious_outputs}

    print("[INFO] Suspicious outputs:")
    for item in suspicious_outputs:
        print(f"  - {item}")

    print("[INFO] Structural mismatch summary:")
    for reason in reasons:
        print(f"  - {reason}")

    cone = backward_cone(suspicious_bases, buggy.assignments)
    print(f"[INFO] Backward cone of influence ({len(cone)} signals): {', '.join(sorted(cone))}")

    cone_diffs = collect_cone_differences(buggy, golden, suspicious_bases)
    if cone_diffs:
        print("[INFO] Differing assignments inside suspicious cone:")
        for lhs in cone_diffs:
            print(f"  - {lhs}")
    else:
        print("[INFO] No direct assign-level mismatches found inside the cone; using output-level replacement.")

    print("[STATUS] Running golden reference simulation...")
    golden_result = run_simulation(
        project.golden_rtl,
        project,
        "golden_reference",
        support_files=project.golden_files[1:],
        include_dirs=project.golden_include_dirs,
    )
    if not golden_result.ok:
        raise RuntimeError(
            "Golden simulation failed.\n"
            f"Compile command: {' '.join(golden_result.compile_cmd)}\n"
            f"Output:\n{golden_result.stdout}"
        )

    print("[INFO] Golden simulation baseline:")
    print(summarize_sim_output(golden_result.stdout))
    reconstructed_summary_path = write_reconstructed_rtl_summary(
        project,
        buggy,
        golden,
        suspicious_outputs,
        cone_diffs,
    )
    reconstructed_candidate_path = write_reconstructed_rtl_candidate(project, golden, suspicious_outputs)
    print(f"[INFO] Reconstructed RTL summary: {reconstructed_summary_path}")
    print(f"[INFO] Reconstructed RTL candidate: {reconstructed_candidate_path}")
    if args.check_only:
        print("[INFO] Check-only mode requested; stopping after feasibility and reconstruction artifacts.")
        return
    planner = Planner()
    if args.executor == "codex":
        if codex_session is None:
            codex_session = ensure_codex_ready(project)
        print(f"[INFO] Codex CLI command: {' '.join(codex_session.command)}")
        executor = CodexExecutor(codex_session, project)
        executor_label = "codex-cli"
    else:
        executor = HeuristicExecutor(project)
        executor_label = "heuristic-assign-rewrite"
    verifier = Verifier(project, golden_stdout=golden_result.stdout)

    print(f"[INFO] Agent architecture: planner=python executor={executor_label} verifier=iverilog/vvp")
    strategies = planner.build_assign_level_strategies(buggy, golden, suspicious_outputs, cone_diffs)

    if not strategies:
        raise RuntimeError("No candidate repair strategies could be generated")

    attempts: List[RepairAttempt] = []
    successful_attempts: List[RepairAttempt] = []
    for index, (strategy_name, lhs_targets) in enumerate(strategies, start=1):
        candidate_name = f"{buggy.module_name}_patched_{index}.v"
        candidate_path = project.output_dir / candidate_name
        print(f"[STATUS] Trying strategy {index}: {strategy_name}")
        print(f"[INFO] Candidate target count: {len(lhs_targets)}")

        candidate_source = executor.generate_assign_level_candidate(buggy, golden, lhs_targets)
        write_candidate(candidate_path, candidate_source)

        result: Optional[SimulationResult] = None
        assessment: Optional[SimulationAssessment] = None
        failure_context = ""
        current_source = candidate_source
        for syntax_attempt in range(args.max_syntax_retries + 1):
            result, assessment, failure_context = verifier.run_candidate(
                candidate_path,
                f"candidate_{index}_try_{syntax_attempt}",
                support_files=project.buggy_support_files,
                include_dirs=[project.base_path / "buggy_netlist"],
            )
            if result.ok or syntax_attempt == args.max_syntax_retries:
                break
            print("[WARN] Candidate failed to compile or run; applying syntax-repair cycle.")
            print(failure_context)
            current_source = executor.generate_assign_level_candidate(
                buggy,
                golden,
                lhs_targets,
                failure_context=failure_context or result.stdout,
            )
            current_source = repair_candidate_syntax(
                current_source,
                result.stdout,
                expected_module=buggy.module_name,
            )
            write_candidate(candidate_path, current_source)

        assert result is not None
        assert assessment is not None
        attempts.append(
            RepairAttempt(
                name=strategy_name,
                candidate_path=candidate_path,
                target_count=len(lhs_targets),
                result=result,
                assessment=assessment,
                failure_context=failure_context,
                syntax_attempts=syntax_attempt + 1,
                executor_mode=args.executor,
            )
        )

        if not result.ok:
            print("[WARN] Candidate failed to compile or run.")
            print(assessment.summary)
            continue

        if assessment.mismatch_detected:
            print("[WARN] Candidate reported mismatch markers in simulation log.")
        if assessment.passed:
            minimality = compute_minimality_score(buggy_source, current_source)
            attempts[-1].minimality_score = minimality
            successful_attempts.append(attempts[-1])
            print(
                "[INFO] Passing candidate minimality: "
                f"hunks={minimality['edit_hunks']} "
                f"lines={minimality['changed_line_count']} "
                f"signals={minimality['changed_signal_count']}"
            )
            continue

        print("[WARN] Candidate simulation does not match golden baseline.")
        print("[INFO] Candidate output:")
        print(assessment.summary)
        if failure_context:
            print("[INFO] Failure context:")
            print(failure_context)

    if successful_attempts:
        best_attempt = min(
            successful_attempts,
            key=lambda item: (
                item.minimality_score["edit_hunks"] if item.minimality_score else 10**9,
                item.minimality_score["changed_line_count"] if item.minimality_score else 10**9,
                item.minimality_score["changed_signal_count"] if item.minimality_score else 10**9,
                item.target_count,
            ),
        )
        best_source = read_text_safe(best_attempt.candidate_path)
        final_path = project.output_dir / f"{buggy.module_name}_patched.v"
        write_candidate(final_path, best_source)
        report_json, report_md = write_patch_report(
            project,
            feasibility,
            buggy,
            golden,
            buggy_source,
            best_source,
            suspicious_outputs,
            best_attempt.assessment,
            minimality=best_attempt.minimality_score,
            reconstructed_summary_path=reconstructed_summary_path,
            reconstructed_candidate_path=reconstructed_candidate_path,
            execution_summary={
                "executor": best_attempt.executor_mode,
                "selected_strategy": best_attempt.name,
                "strategy_attempts": len(attempts),
                "successful_candidates": len(successful_attempts),
                "syntax_attempts_for_selected_candidate": best_attempt.syntax_attempts,
            },
        )
        print(f"[SUCCESS] Repaired netlist written to {final_path}")
        print(
            "[INFO] Selected minimal passing patch: "
            f"hunks={best_attempt.minimality_score['edit_hunks']} "
            f"lines={best_attempt.minimality_score['changed_line_count']} "
            f"signals={best_attempt.minimality_score['changed_signal_count']}"
        )
        print(f"[INFO] Patch reports: {report_json}, {report_md}")
        print("[INFO] Matching simulation transcript:")
        print(summarize_sim_output(best_attempt.result.stdout))
        return

    failed_payload = build_failure_report_payload(
        feasibility,
        assessment=attempts[-1].assessment if attempts else None,
        failure_context=attempts[-1].failure_context if attempts else "",
    )
    write_report_files(project, "patch_report", failed_payload)
    raise RuntimeError("All candidate repair strategies failed to match the golden simulation output")


def main() -> None:
    try:
        run_repair_cycle()
    except Exception as error:
        print(f"[FATAL] {error}")
        raise


if __name__ == "__main__":
    main()
