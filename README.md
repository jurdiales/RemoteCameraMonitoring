# Remote Camera Monitoring

A Python-based live camera streaming system with WebRTC, Flask, OpenCV, and a Tkinter launcher.

Stream webcam video and microphone audio to a browser, with optional motion detection, auto-recording, and secure access.

## Features

- **WebRTC live streaming** for low-latency browser playback
- **MJPEG/WebSocket fallback** for compatibility
- **Tkinter GUI launcher** for camera, audio, resolution, framerate, and port selection
- **Motion detection** and **automatic recording**
- **Password authentication** and **HTTPS/TLS** support
- **Cross-platform** support for Windows, macOS, and Linux

## Requirements

- Python 3.10+
- Webcam and audio input device
- `pip install -r requirements.txt` (or `pip install .` for package install)

## Quick Start

1. **Install dependencies**:
   ```bash
   python -m pip install -r requirements.txt
   ```

2. **Launch the Application**:
   ```bash
   python gui.py
   ```

3. **Configure & Start**:
   - In the Launcher window, select your desired **Camera** and **Audio** devices.
   - Adjust the **Resolution** and **FPS** if necessary.
   - Click the green **▶ START SERVER** button.
   - Open your browser and go to `http://localhost:8090` (or the port you configured).

## Package Install

1. **Regular install** (recommended):
   ```bash
   pip install .
   ```

2. **Development** (editable install — changes take effect immediately):
   ```bash
   pip install -e .
   ```

3. **Run GUI launcher:**
   ```bash
   remotecamera
   # OR
   python -m RemoteCameraMonitoring
   ```

4. **Run headless server directly:**
   ```bash
   remotecameraserver --camera 0 --port 8090
   # OR
   python -m RemoteCameraMonitoring.server --camera 0 --port 8090
   ```
   *(Note: all CLI flags available, , please read **[SETUP.md](SETUP.md)**)*

## Security

This section describes how to secure your camera stream with password authentication and HTTPS.

### Password Authentication

By default, the web interface is **not protected**. To add password protection:

#### Option 1: Generate a secure hash (recommended)

Generate a password hash once and reuse it:

```bash
python -m RemoteCameraMonitoring.password
```

This will prompt you to enter a password twice, then output a secure PBKDF2-SHA256 hash.

Then, you can put the hash on the GUI launcher, or start the server directly using one of:

1. **Via environment variable:**
   ```bash
   # On Windows
   $Env:REMOTE_CAMERA_PASSWORD_HASH="pbkdf2_sha256%260000%..."
   # On Linux
   export REMOTE_CAMERA_PASSWORD_HASH="pbkdf2_sha256%260000%..."
   # To run the server directly
   python -m RemoteCameraMonitoring.server
   ```

2. **Via CLI argument:**
   ```bash
   python -m RemoteCameraMonitoring.server --password-hash "pbkdf2_sha256%260000%..."
   ```
*(Note: if the environment variable REMOTE_CAMERA_PASSWORD_HASH is already set, it will appear on the GUI launcher and will be used by the server)*

For development only, the password can be entered in plain text (it will be hashed in memory on startup):

```bash
python -m RemoteCameraMonitoring.server --password "MySecurePassword123"
```

### HTTPS / TLS Support (Remote Access)

To run the server over HTTPS, needed for correct remote access, provide a certificate and private key:

```bash
python -m RemoteCameraMonitoring.server --ssl-cert /path/to/cert.pem --ssl-key /path/to/key.pem
```

**Self-signed certificate example:**
```bash
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes
```

Then access the server at `https://localhost:8090` (accept the browser warning for self-signed certs).

### Security Best Practices

1. **Use hashed passwords** — store `REMOTE_CAMERA_PASSWORD_HASH` in a secure location, never commit it to version control.
2. **Use HTTPS** — especially when accessing remotely, as many mobile browsers require a Secure Context (HTTPS) to allow WebRTC connections to work correctly.
3. **Keep Python and dependencies updated** — run `pip install --upgrade -r requirements.txt`.
4. **Use strong passwords** — minimum 12 characters with mixed case, numbers, and symbols.
5. **Change passwords periodically** — regenerate hashes and update your configuration.

## Documentation

See **[SETUP.md](SETUP.md)** for detailed setup, remote access, and troubleshooting.

Additional technical notes are available in the `doc/` folder:
- `doc/RemoteConnection.md`
- `doc/StreamTechnologies.md`

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
