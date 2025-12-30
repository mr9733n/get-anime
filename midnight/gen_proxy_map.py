# tools/gen_proxy_map.py
from __future__ import annotations

import ast
import importlib
import pkgutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


# --- настрой это под свою структуру (по умолчанию под твою) ---
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTROLLERS_DIR = PROJECT_ROOT / "app" / "qt" / "controllers"
APP_MODULE = "app.qt.app"
APP_CLASS = "AnimePlayerAppVer3"
CALLBACK_KEYWORDS = {
    "callback", "cb", "handler", "action",
    "on_click", "on_change", "on_submit",
    "play_link", "open_web_link", "display_info", "display_titles",
}

# В твоём проекте атрибуты оркестратора называются так.
# Можно расширять при необходимости.
KNOWN_CONTROLLER_ATTRS = {
    "players": "player",
    "player": "player",
    "posters": "poster",
    "poster": "poster",
    "display": "display",
    "torrent": "torrent",
    "actions": "actions",
    "state_runtime": "state_runtime",
    "animedia": "animedia",
    "aniliberty": "aniliberty",
    "persistence": "persistence",
    "callback": "callback",
    "bootstrap": "bootstrap",
}


@dataclass(frozen=True)
class AppCall:
    method: str
    file: Path
    lineno: int


def iter_py_files(d: Path) -> List[Path]:
    return sorted([p for p in d.glob("*.py") if p.is_file() and not p.name.startswith("_") and "tests" not in p.parts])


def parse_tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def collect_app_callable_uses(path: Path) -> tuple[list[AppCall], list[AppCall]]:
    tree = parse_tree(path)
    called, refs = [], []

    def is_self_app(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Attribute)
            and node.attr == "app"
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
        )

    class V(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            # self.app.<name>(...)
            f = node.func
            if isinstance(f, ast.Attribute) and is_self_app(f.value):
                called.append(AppCall(method=f.attr, file=path, lineno=getattr(node, "lineno", 0)))

            # keyword callbacks: foo=self.app.<name>
            for kw in node.keywords or []:
                if kw.arg and kw.arg in CALLBACK_KEYWORDS:
                    v = kw.value
                    if isinstance(v, ast.Attribute) and is_self_app(v.value):
                        refs.append(AppCall(method=v.attr, file=path, lineno=getattr(node, "lineno", 0)))

            self.generic_visit(node)

        def visit_Assign(self, node: ast.Assign) -> None:
            # callbacks[...] = self.app.<name>
            v = node.value
            if isinstance(v, ast.Attribute) and is_self_app(v.value):
                # только если присваиваем в dict/list с "callback-like" именем
                for t in node.targets:
                    if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name):
                        if t.value.id.lower() in {"callbacks", "actions", "handlers"}:
                            refs.append(AppCall(method=v.attr, file=path, lineno=getattr(node, "lineno", 0)))
            self.generic_visit(node)

    V().visit(tree)
    return called, refs

def collect_controller_methods(path: Path) -> Set[str]:
    """
    Собираем имена методов, объявленных в классах в файле контроллера.
    """
    tree = parse_tree(path)
    methods: Set[str] = set()

    class V(ast.NodeVisitor):
        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    methods.add(item.name)
            self.generic_visit(node)

    V().visit(tree)
    return methods


def guess_controller_attr(controller_file: Path) -> Optional[str]:
    stem = controller_file.stem
    # players.py -> player, posters.py -> poster, etc.
    return KNOWN_CONTROLLER_ATTRS.get(stem)


def load_existing_proxy_map() -> Dict[str, Tuple[str, str]]:
    mod = importlib.import_module(APP_MODULE)
    cls = getattr(mod, APP_CLASS)
    proxy_map = getattr(cls, "_PROXY_MAP", None)
    if proxy_map is None:
        return {}
    # нормализуем на всякий случай
    out: Dict[str, Tuple[str, str]] = {}
    for k, v in dict(proxy_map).items():
        if isinstance(v, (list, tuple)) and len(v) == 2:
            out[str(k)] = (str(v[0]), str(v[1]))
    return out


def main() -> None:
    if not CONTROLLERS_DIR.exists():
        raise SystemExit(f"Controllers dir not found: {CONTROLLERS_DIR}")

    controller_files = iter_py_files(CONTROLLERS_DIR)

    # 1) Собираем вызовы self.app.<method>()
    app_calls: List[AppCall] = []
    for f in controller_files:
        app_calls.extend(collect_app_callable_uses(f))

    called_methods: Set[str] = {c.method for c in app_calls}

    # 2) Собираем "где определён метод" (method -> controller_attr)
    method_to_ctrl: Dict[str, str] = {}
    ambiguous: Dict[str, List[str]] = {}

    for f in controller_files:
        ctrl_attr = guess_controller_attr(f)
        if not ctrl_attr:
            continue
        methods = collect_controller_methods(f)
        for m in methods:
            if m in method_to_ctrl and method_to_ctrl[m] != ctrl_attr:
                ambiguous.setdefault(m, sorted({method_to_ctrl[m], ctrl_attr}))
            else:
                method_to_ctrl[m] = ctrl_attr

    # 3) Читаем существующую карту
    existing = load_existing_proxy_map()
    existing_keys = set(existing.keys())

    missing = sorted(called_methods - existing_keys)
    extra = sorted(existing_keys - called_methods)

    # 4) Генерим карту (полную или только missing)
    def render_entry(name: str) -> str:
        ctrl = method_to_ctrl.get(name, "???")
        if name in ambiguous:
            ctrl = "???"
        return f'    "{name}": ("{ctrl}", "{name}"),'

    print("\n=== Proxy map audit ===")
    print(f"Controllers scanned: {len(controller_files)}")
    print(f"Unique self.app.* calls found: {len(called_methods)}")
    print(f"Existing _PROXY_MAP keys: {len(existing_keys)}")

    if missing:
        print(f"\nMissing in _PROXY_MAP: {len(missing)}")
        for m in missing:
            # покажем, где встречается
            locs = [c for c in app_calls if c.method == m]
            sample = ", ".join([f"{c.file.name}:{c.lineno}" for c in locs[:5]])
            tail = "" if len(locs) <= 5 else f" (+{len(locs) - 5} more)"
            print(f"  - {m}  [{sample}{tail}]")
    else:
        print("\nMissing in _PROXY_MAP: 0 ✅")

    if extra:
        print(f"\nExtra in _PROXY_MAP (nobody calls): {len(extra)}")
        for m in extra:
            print(f"  - {m} -> {existing[m]}")
    else:
        print("\nExtra in _PROXY_MAP: 0 ✅")

    if ambiguous:
        print("\nAmbiguous method owners (defined in >1 controller file):")
        for m, owners in sorted(ambiguous.items()):
            print(f"  - {m}: {owners}")

    # Печатаем готовый блок для вставки
    if missing:
        print("\n=== Suggested _PROXY_MAP additions (paste into app.py) ===")
        print("{")
        for m in missing:
            print(render_entry(m))
        print("}")
        print("\nNOTE: entries with ctrl='???' need manual fix (method not found or ambiguous).")


if __name__ == "__main__":
    main()
