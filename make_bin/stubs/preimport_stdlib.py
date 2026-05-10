"""
preimport_stdlib.py — PyInstaller analysis helper.

This file is listed as an EXTRA SCRIPT in Analysis() so PyInstaller's static
analyser walks its imports and bundles every referenced module.  It is NOT
executed at runtime — only the first Analysis script (server.py / launcher.py)
runs on startup.

WHY THIS EXISTS
---------------
PyInstaller's `hiddenimports` list adds module names verbatim; it does NOT
re-analyse those modules for their own imports.  The result is that
`http.client` (and the entire urllib / email chain) ends up missing even when
listed in hiddenimports, producing:

    WARNING: Hidden import "http.client" not found!

and the runtime crash:

    ModuleNotFoundError: No module named 'http.client'

Adding this file to Analysis(scripts=[..., THIS_FILE]) forces the full static
analysis pass, so the complete transitive closure is collected automatically.
"""

# --- http / urllib / email chain needed by pyi_rth_pkgres at startup ---
import http
import http.client
import http.cookiejar
import http.cookies
import http.server
import urllib
import urllib.error
import urllib.parse
import urllib.request
import urllib.response
import urllib.robotparser
import email
import email.charset
import email.encoders
import email.errors
import email.feedparser
import email.generator
import email.header
import email.message
import email.mime
import email.mime.base
import email.mime.multipart
import email.mime.text
import email.parser
import email.policy
import email.utils
import html
import html.entities
import html.parser

# --- Other stdlib modules commonly missed by the analyser ---
import base64
import binascii
import ssl
import socket
import socketserver
