"""
PyInstaller entry script for the HTTP backend.

Do not point Analysis() directly at backend/transport/http/server.py.
When that file is used as the entry script, PyInstaller treats
backend/transport/http as a top-level package named "http", which shadows the
Python stdlib http package and breaks imports such as urllib.request ->
http.client at runtime.
"""

from backend.transport.http.server import main


if __name__ == "__main__":
    main()
