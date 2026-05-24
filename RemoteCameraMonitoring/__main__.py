# RemoteCameraMonitoring/__main__.py
"""
Entry points:
    python -m RemoteCameraMonitoring            → GUI launcher (Pyside)
    python -m RemoteCameraMonitoring legacy     → GUI launcher (Tkinter)
    python -m RemoteCameraMonitoring.server     → headless server (all CLI flags available)
"""

import sys


def main():
    from .qtgui import main as gui_main
    sys.exit(gui_main())

def legacy():
    from .gui import main as gui_main
    sys.exit(gui_main())

def server():
    from .server import main as server_main
    sys.exit(server_main())


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "legacy":
            legacy()
        else:
            main()
    else:
        main()
