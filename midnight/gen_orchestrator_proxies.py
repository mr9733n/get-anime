from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
QT_DIR = PROJECT_ROOT / "app" / "qt"
CONTROLLERS_DIR = QT_DIR / "controllers"

PROXY_API_PY = QT_DIR / "proxy_api.py"
OUT_PY = QT_DIR / "orchestrator_proxies.py"


# controller_attr -> controller source file
# подправь/добавь, если у тебя другое именование
CTRL_FILE: Dict[str, Path] = {
    "bootstrap": CONTROLLERS_DIR / "bootstrap.py",
    "display": CONTROLLERS_DIR / "display.py",
    "player": CONTROLLERS_DIR / "players.py",
    "poster": CONTROLLERS_DIR / "posters.py",
    "torrent": CONTROLLERS_DIR / "torrents.py",
    "actions": CONTROLLERS_DIR / "actions.py",
    "animedia": CONTROLLERS_DIR / "animedia.py",
    "aniliberty": CONTROLLERS_DIR / "aniliberty.py",
    "persistence": CONTROLLERS_DIR / "persistence.py",
    "callback": CONTROLLERS_DIR / "callback.py",
    "state_runtime": CONTROLLERS_DIR / "state_runtime.py",
}


@dataclass(frozen=True)
class ProxyEntry:
    public: str
    ctrl: str
    meth: str


def parse_ast(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def literal(node: ast.AST):
    """Safe conversion for dict/tuple/list/str literals used in PROXY_API."""
    if isinstance(node, ast.Dict):
        return {literal(k): literal(v) for k, v in zip(node.keys, node.values)}
    if isinstance(node, (ast.Tuple, ast.List)):
        return tuple(literal(x) for x in node.elts)
    if isinstance(node, ast.Constant):
        return node.value
    raise ValueError(f"Unsupported literal: {type(node).__name__}")


def load_proxy_api(proxy_api_path: Path) -> Dict[str, Tuple[str, str]]:
    """
    Reads:
        PROXY_API: Dict[str, Tuple[str, str]] = { ... }
    Supports both Assign and AnnAssign.
    """
    tree = parse_ast(proxy_api_path)

    for node in tree.body:
        # PROXY_API = {...}
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "PROXY_API":
                    obj = literal(node.value)
                    return _normalize_proxy_map(obj)

        # PROXY_API: ... = {...}
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "PROXY_API":
                if node.value is None:
                    raise SystemExit("PROXY_API AnnAssign has no value")
                obj = literal(node.value)
                return _normalize_proxy_map(obj)

    raise SystemExit(f"Cannot find PROXY_API in {proxy_api_path}")


def _normalize_proxy_map(obj) -> Dict[str, Tuple[str, str]]:
    out: Dict[str, Tuple[str, str]] = {}
    if not isinstance(obj, dict):
        raise SystemExit("PROXY_API must be a dict literal")
    for k, v in obj.items():
        if not isinstance(k, str):
            continue
        if not (isinstance(v, tuple) and len(v) == 2):
            continue
        ctrl, meth = v
        out[k] = (str(ctrl), str(meth))
    return out


def collect_defs(path: Path) -> Set[str]:
    """Collect all 'def <name>' inside the file (any class or module-level)."""
    tree = parse_ast(path)
    names: Set[str] = set()

    class V(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            names.add(node.name)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            names.add(node.name)
            self.generic_visit(node)

    V().visit(tree)
    return names


def validate(entries: Iterable[ProxyEntry]) -> None:
    errors: List[str] = []

    # 1) базовая валидация значений
    for e in entries:
        if not e.public.isidentifier():
            errors.append(f"'{e.public}': not a valid python identifier (cannot generate def {e.public}(...))")
        if not e.ctrl or e.ctrl == "???":
            errors.append(f"'{e.public}': controller is empty/???")
        if not e.meth or e.meth == "???":
            errors.append(f"'{e.public}': method is empty/???")
        if e.ctrl and e.ctrl not in CTRL_FILE:
            errors.append(f"'{e.public}': unknown controller '{e.ctrl}' (add to CTRL_FILE map)")

    # 2) проверка существования методов в файлах контроллеров
    #    (по AST — без импортов Qt)
    ctrl_methods_cache: Dict[str, Set[str]] = {}
    for e in entries:
        if e.ctrl in CTRL_FILE:
            f = CTRL_FILE[e.ctrl]
            if not f.exists():
                errors.append(f"controller '{e.ctrl}' file not found: {f}")
                continue
            if e.ctrl not in ctrl_methods_cache:
                ctrl_methods_cache[e.ctrl] = collect_defs(f)
            if e.meth not in ctrl_methods_cache[e.ctrl]:
                errors.append(f"'{e.public}': {e.ctrl}.{e.meth} not found in {f.name}")

    if errors:
        print("\nProxy API validation failed:\n", file=sys.stderr)
        for msg in errors:
            print(f"  - {msg}", file=sys.stderr)
        raise SystemExit(2)


def render(entries: List[ProxyEntry]) -> str:
    lines: List[str] = []
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("class OrchestratorProxies:")
    lines.append('    """')
    lines.append("    Auto-generated proxies for AnimePlayerAppVer3.")
    lines.append("    DO NOT EDIT MANUALLY.")
    lines.append("    Regenerate via: python midnight/gen_orchestrator_proxies.py")
    lines.append('    """')
    lines.append("")

    for e in sorted(entries, key=lambda x: x.public):
        lines.append(f"    def {e.public}(self, *args, **kwargs):")
        lines.append(f'        """Proxy -> self.{e.ctrl}.{e.meth}"""')
        lines.append(f"        return self.{e.ctrl}.{e.meth}(*args, **kwargs)")
        lines.append("")

    if len(entries) == 0:
        lines.append("    pass")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    proxy_map = load_proxy_api(PROXY_API_PY)
    entries = [ProxyEntry(public=k, ctrl=v[0], meth=v[1]) for k, v in proxy_map.items()]

    validate(entries)

    OUT_PY.write_text(render(entries), encoding="utf-8")
    print(f"WROTE: {OUT_PY.relative_to(PROJECT_ROOT)} ({len(entries)} proxies)")


if __name__ == "__main__":
    main()
