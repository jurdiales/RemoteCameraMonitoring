# Remote Camera Monitoring

Remote camera broadcast system using Python, WebRTC, and Flask.

## Features

- **WebRTC Video & Audio Streaming**: Real-time, low-latency transmission using `aiortc`.
- **Graphical Launcher**: A built-in Tkinter GUI (`gui.py`) for easy configuration of cameras, microphones, resolution, framerate, and network settings.
- **Audio Support**: Captures system audio or microphone streams seamlessly alongside video.
- **Motion Detection**: Built-in motion detection capabilities.
- **Auto-Recording**: Automatically save video clips when motion is detected.
- **Remote Access**: Stream your camera securely from outside your local network. See HTTPS / TLS support below.

## Requirements

- Python 3.10+
- A connected webcam and an audio input device.

## Quick Start

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   *(Note: The GUI uses `pygrabber` for discovering audio/video devices on Windows. This is automatically installed if you follow the requirements)*

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

1. **Development** (editable install — changes take effect immediately):
   ```bash
   cd FOLDER_WHERE_THIS_FILE_IS
   pip install -e .
   ```

2. **Regular install** (recommended):
   ```bash
   cd FOLDER_WHERE_THIS_FILE_IS
   pip install .
   ```

3. **Run GUI launcher:**
   ```bash
   python -m RemoteCameraMonitoring
   ```
   Once installed, the GUI can be launched using the script **remotecamera** on a terminal:
   ```bash
   remotecamera
   ```

4. **Run headless server directly:**
   ```bash
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

#### Option 2: Direct password (less secure)

For development only, passwords are hashed on startup. The password can be entered 

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

For a complete step-by-step installation guide, advanced configuration, and instructions on how to access the camera remotely from outside your home network, please read the **[SETUP.md](SETUP.md)** file (Available in Spanish).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
