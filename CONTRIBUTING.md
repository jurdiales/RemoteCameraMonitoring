# Contributing to Remote Camera Monitoring

Thank you for your interest in contributing! This document provides a guide for developers looking to understand and modify the codebase.

## Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/jurdiales/RemoteCameraMonitoring.git
   cd RemoteCameraMonitoring
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   # On Windows
   venv\Scripts\activate
   # On Linux/macOS
   source venv/bin/activate
   ```

3. **Install in editable mode**:
   This allows you to modify the code and see changes immediately without re-installing.
   ```bash
   pip install -e .
   ```

## Project Structure

- `RemoteCameraMonitoring/` — Main package directory.
  - `__main__.py` — Entry point for the package (runs the GUI or server).
  - `gui.py` — Tkinter-based launcher and configuration interface.
  - `server.py` — Flask-based server handling WebRTC, WebSockets, and motion detection.
  - `utils.py` — Hardware enumeration and helper functions.
  - `password.py` — Password hashing and verification utilities.
  - `templates/` — HTML/JS for the web interface.
  - `resources/` — Icons and images for the GUI.
- `doc/` — Additional technical documentation.
- `recordings/` — Default directory for motion-triggered recordings (created on launch).
- `setup.py` — Packaging configuration.

## Coding Standards

- **Python**: Use Python 3.10+. Follow PEP 8 where possible.
- **WebRTC**: We use `aiortc` for the server-side WebRTC implementation.
- **Frontend**: The web interface uses vanilla JavaScript and CSS for maximum compatibility and performance.

## Testing Changes

Before submitting a pull request, please test:
1. **Local streaming**: Run `remotecamera` and verify the stream works on `localhost`.
2. **Audio**: Ensure audio is captured and audible in the browser.
3. **Motion Detection**: Verify that motion triggers recordings (check the `recordings/` folder).
4. **HTTPS**: Test with a self-signed certificate to ensure WebRTC works over a secure context.

## Reporting Issues

If you find a bug or have a feature request, please open an issue on the GitHub repository.
