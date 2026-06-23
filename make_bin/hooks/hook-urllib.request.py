# make_bin/hooks/hook-urllib.request.py
"""
PyInstaller hook for urllib.request.

PyInstaller's static analyser detects `import urllib.request` but does NOT
follow urllib.request's own top-level imports.  Those imports include:

    import http.client
    import http.cookiejar
    import urllib.error
    import urllib.parse
    import urllib.response
    import email.message
    import base64
    import ssl

Without this hook every binary that uses urllib (directly or via requests /
setuptools / pyi_rth_pkgres) crashes at startup with:

    ModuleNotFoundError: No module named 'http.client'

This hook fires whenever urllib.request is collected and adds the full
transitive closure of stdlib modules it needs.
"""
from PyInstaller.utils.hooks import collect_submodules

# Collect every submodule of each package so we don't have to list them
# individually and miss one when Python adds a new import.
hiddenimports = (
    collect_submodules("http")      # http.client, http.cookiejar, http.cookies …
    + collect_submodules("urllib")  # urllib.error, urllib.parse, urllib.response …
    + collect_submodules("email")   # email.message, email.generator, email.policy …
    + collect_submodules("html")    # html.parser …
    + [
        "base64",
        "ssl",
        "binascii",
        "quopri",
        "uu",
    ]
)

print(f"[hook-urllib.request] injecting {len(hiddenimports)} stdlib hidden imports")
