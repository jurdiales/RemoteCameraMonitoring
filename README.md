# Remote Camera Monitoring

Remote camera broadcast system using Python, WebRTC, and Flask.

## Features

- **WebRTC Video & Audio Streaming**: Real-time, low-latency transmission using `aiortc`.
- **Graphical Launcher**: A built-in Tkinter GUI (`gui.py`) for easy configuration of cameras, microphones, resolution, framerate, and network settings.
- **Audio Support**: Captures system audio or microphone streams seamlessly alongside video.
- **Motion Detection**: Built-in motion detection capabilities.
- **Auto-Recording**: Automatically save video clips when motion is detected.
- **Remote Access**: Stream your camera securely from outside your local network.

## Requirements

- Python 3.9+
- Windows (for the device discovery via `pygrabber` and the GUI)
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

## Documentation

For a complete step-by-step installation guide, advanced configuration, and instructions on how to access the camera remotely from outside your home network, please read the **[SETUP.md](SETUP.md)** file (Available in Spanish).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
