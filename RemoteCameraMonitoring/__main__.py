# RemoteCameraMonitoring/__main__.py
"""
Entry points:
    python -m RemoteCameraMonitoring            → GUI launcher
    python -m RemoteCameraMonitoring.server     → headless server (all CLI flags available)
"""

import sys


def main():
    from .gui import main as gui_main
    sys.exit(gui_main())

def server():
    from .server import main as server_main
    sys.exit(server_main())


if __name__ == "__main__":
    main()
