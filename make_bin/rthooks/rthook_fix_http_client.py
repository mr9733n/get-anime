# make_bin/rthooks/rthook_fix_http_client.py
"""
PyInstaller runtime hook — runs BEFORE every package runtime hook,
including the built-in pyi_rth_pkgres.

Problem
-------
PyInstaller's pyi_rth_pkgres runtime hook fires at process start and
triggers this import chain:

    pkg_resources
      → setuptools._vendor.jaraco.text
        → setuptools._vendor.jaraco.context
          → urllib.request
            → http.client   ← ModuleNotFoundError on Python 3.13+

On Python 3.13 PyInstaller's static analyser sometimes cannot locate
the compiled form of stdlib modules (it reports
  "WARNING: Hidden import 'http.client' not found!"
even though http/client.py exists on disk).  The module ends up absent
from the bundle, causing a crash the moment pyi_rth_pkgres tries to
import it.

Fix
---
Pre-import the entire http / urllib / email chain here, BEFORE
pyi_rth_pkgres runs.  Python caches every successful import in
sys.modules, so when pyi_rth_pkgres later does `import http.client`
it gets the cached object immediately — no file lookup, no crash.

If the module is missing from the bundle we fall back to adding the
live Python installation's stdlib directory to sys.path, then retry.
This fallback works on the developer's own machine where Python 3.13
is installed alongside the binary.
"""
import sys
import os


def _preload_http_chain():
    # Full chain that pyi_rth_pkgres transitively needs
    _MODULES = [
        "http",
        "http.client",
        "http.cookiejar",
        "http.cookies",
        "http.server",
        "urllib",
        "urllib.error",
        "urllib.parse",
        "urllib.request",
        "urllib.response",
        "urllib.robotparser",
        "email",
        "email.charset",
        "email.encoders",
        "email.errors",
        "email.feedparser",
        "email.generator",
        "email.header",
        "email.message",
        "email.mime",
        "email.mime.base",
        "email.mime.multipart",
        "email.mime.text",
        "email.parser",
        "email.policy",
        "email.utils",
        "html",
        "html.entities",
        "html.parser",
        "base64",
        "binascii",
        "ssl",
        "socket",
        "socketserver",
    ]

    missing = []
    for name in _MODULES:
        try:
            __import__(name)
        except ImportError:
            missing.append(name)

    if not missing:
        return  # All modules already importable from the bundle — done.

    # ── Fallback: patch sys.path with the live Python stdlib ─────────────────
    # Strategy 1: sysconfig (most reliable cross-platform)
    try:
        import sysconfig as _sc
        stdlib = _sc.get_path("stdlib")
        if stdlib and os.path.isdir(stdlib) and stdlib not in sys.path:
            sys.path.insert(0, stdlib)
    except Exception:
        pass

    # Strategy 2: prefix-based guesses (Windows Lib/, Unix lib/pythonX.Y/)
    try:
        prefix = getattr(sys, "base_prefix", None) or sys.prefix
        candidates = [
            os.path.join(prefix, "Lib"),                                          # Windows
            os.path.join(prefix, "lib", "python%d.%d" % sys.version_info[:2]),   # Linux/macOS
        ]
        for path in candidates:
            if os.path.isdir(path) and path not in sys.path:
                sys.path.insert(0, path)
                break
    except Exception:
        pass

    # Re-try every module that was missing; ignore failures (best-effort).
    for name in missing:
        try:
            __import__(name)
        except ImportError:
            pass


_preload_http_chain()
del _preload_http_chain
