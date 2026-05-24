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

To stream video and audio remotely, modern mobile and desktop browsers **require** a **Secure Context (HTTPS)** to allow WebRTC connections. You have two ways to configure HTTPS:

#### Option 1: Automatic HTTPS with Caddy (Recommended & Easiest)
**Caddy** is a modern, lightweight web server that automatically provisions and renews TLS/SSL certificates. We use Caddy to act as a secure reverse proxy in front of our Flask server, meaning you get fully secure local network HTTPS without managing certificates!

1. **Download Caddy**: Download the `caddy.exe` binary for your OS from the [official Caddy download page](https://caddyserver.com/download).
2. **Place in Resources**: Put `caddy.exe` inside the `resources/` folder in your project (`D:\Code\RemoteCameraMonitoring\resources\caddy.exe`).
3. **Enable via GUI**: Open `python gui.py`, check the **Enable HTTPS with Caddy** checkbox under **FEATURES**, and click **START SERVER**.
4. **Access your server**: The application will automatically launch and manage Caddy. You can now access your stream securely at:
   - `https://localhost` (locally)
   - `https://<your-local-ip>` (from other devices on your home network)

*Note: Caddy uses an internal certificate authority. On your first visit, your browser might show a certificate warning. You can safely bypass this or install Caddy's root certificate on your device to make it fully trusted.*

#### Option 2: Manual SSL Certificates
If you prefer not to use Caddy, you can provide your own certificate and private key files directly:

```bash
python -m RemoteCameraMonitoring.server --ssl-cert /path/to/cert.pem --ssl-key /path/to/key.pem
```

**Generating a self-signed certificate:**
```bash
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes
```
Then access the server at `https://localhost:8090` (and accept the browser warning).

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
