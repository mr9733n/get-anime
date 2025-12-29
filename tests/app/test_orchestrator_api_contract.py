import ast
import inspect
from pathlib import Path
import logging
logging.getLogger(__name__).setLevel(logging.CRITICAL)

from app.qt.app import AnimePlayerAppVer3


def iter_controller_files():
    controllers_dir = Path(__file__).resolve().parents[1] / "app" / "qt" / "controllers"
    for p in controllers_dir.glob("*.py"):
        if p.name.startswith("_"):
            continue
        yield p


def collect_app_calls(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text(encoding="utf-8"))
    names = set()

    class V(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call):
            # match: self.app.<name>(...)
            f = node.func
            if isinstance(f, ast.Attribute) and f.attr:
                v = f.value
                if isinstance(v, ast.Attribute) and v.attr == "app":
                    if isinstance(v.value, ast.Name) and v.value.id == "self":
                        names.add(f.attr)
            self.generic_visit(node)

    V().visit(tree)
    return names


def test_all_controller_calls_are_exposed_on_orchestrator():
    exposed = set(dir(AnimePlayerAppVer3))
    missing = {}

    for file in iter_controller_files():
        calls = collect_app_calls(file)
        for name in sorted(calls):
            if name not in exposed:
                missing.setdefault(file.name, []).append(name)

    assert not missing, "Missing orchestrator proxy methods:\n" + "\n".join(
        f"- {fname}: {', '.join(names)}" for fname, names in missing.items()
    )

