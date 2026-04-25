# Remote Camera Monitoring — Installation and Configuration Guide
## Home surveillance system for pets

---

## 1. Prerequisites

- **Python 3.9 or higher** — download from https://python.org  
  ⚠️ During installation, check the **"Add Python to PATH"** option
- **Webcam** connected to the laptop (USB or built-in)
- Laptop **always on and connected to the network** while you want to monitor

---

## 2. Installing Dependencies

Open the **Command Prompt (CMD)** or **PowerShell** and run:

```
cd C:\path\to\where\you\saved\the\files
pip install -r requirements.txt
```

If `pip` is not recognized, try:
```
python -m pip install -r requirements.txt
```

---

## 3. Starting the Server

```
python gui.py
```

A configuration window (Launcher) will open where you can:
- Select your **Camera** and **Audio** device (Microphone).
- Configure the **Resolution**, **FPS** (frames per second), and the network **Port**.
- Enable or disable features like **Motion Detection** and **Recording**.

Click the green **▶ START SERVER** button and wait a few seconds. In the console on the right, you will see something like this:
```
Server Local Access: http://localhost:8090
```

Open **http://localhost:8090** in the browser of the same laptop to verify that it works.

> **No image or sound?** Check in the Launcher that you have selected the correct camera and audio device before starting the server.

---

## 4. Remote Access via Port Forwarding

This is the most important part to view the camera from outside your home.

### 4.1 Find your laptop's local IP

In CMD run:
```
ipconfig
```
Look for the **IPv4 Address** line under your Wi-Fi or Ethernet adapter.
Example: `192.168.1.105`

**Write down this IP** — you will need it in step 4.3.

### 4.2 Assign a static IP to your laptop (recommended)

To prevent the local IP from changing after each router reboot:

1. Go to **Settings → Network & Internet → Wi-Fi → Hardware properties**
2. Select **Edit** under "IP assignment"
3. Change to **Manual** and turn on IPv4
4. Enter:
   - IP Address: `192.168.1.105` (the one you wrote down above)
   - Subnet mask: `255.255.255.0`
   - Gateway: your router's IP (usually `192.168.1.1`)
   - Preferred DNS: `8.8.8.8`

### 4.3 Configure Port Forwarding on your router

The interface varies by manufacturer, but the process is similar:

1. Open a browser and go to your router's address:
   - Movistar/O2: `192.168.1.1`
   - Vodafone: `192.168.0.1`
   - Orange: `192.168.1.1`
2. Enter the username and password (usually on the router's sticker)
3. Look for the section: **"Port Forwarding"**, **"NAT"**, **"Virtual Servers"** or similar
4. Create a new rule with these details:

   | Field              | Value                         |
   |--------------------|-------------------------------|
   | Name / Service     | `RemoteMonitoring`                    |
   | Protocol           | `TCP`                         |
   | External port      | `8090`                        |
   | Internal port      | `8090`                        |
   | Destination IP     | `192.168.1.105` (the laptop's IP) |
   | Status             | Enabled / Active              |

5. Save and restart the router if prompted.

### 4.4 Find your public IP

Go to https://www.whatismyip.com — it will show you your public IP.  
Example: `88.12.34.56`

⚠️ **This IP can change** if your ISP uses dynamic IPs (which is standard).  
Check section 5 to fix this.

### 4.5 Access from outside

From any device with mobile data or a different network, open:
```
http://88.12.34.56:8090
```

You can now watch your canary and lovebird from anywhere!

---

## 5. Dynamic IP — Set up a free domain name (DDNS)

If your public IP changes, you need a DDNS service to give you a fixed name.

### Recommended option: DuckDNS (free and simple)

1. Go to https://www.duckdns.org and log in with Google or GitHub
2. Create a subdomain, for example: `my-birds.duckdns.org`
3. Download the **Windows client** from the same website so it updates
   your IP automatically in the background
4. From now on, access with:
   ```
   http://my-birds.duckdns.org:8090
   ```

---

## 6. Open the port in Windows Firewall

If external access doesn't work, the firewall might be blocking it:

1. Open **Control Panel → System and Security → Windows Defender Firewall**
2. Click on **Advanced settings**
3. **Inbound Rules → New Rule**
4. Type: **Port** → TCP → Specific local ports: `8090`
5. Action: **Allow the connection**
6. Apply to: Domain, Private and Public
7. Name: `RemoteMonitoring`

---

## 7. Automatic startup with Windows

For the server to start automatically when you turn on the laptop:

1. Create a `start_RemoteMonitoring.bat` file with this content:
   ```batch
   @echo off
   cd /d C:\path\to\where\you\saved\the\files
   python gui.py
   ```
2. Press `Win + R`, type `shell:startup` and press Enter
3. Copy (or create a shortcut to) `start_RemoteMonitoring.bat` into that folder

*(Note: When using `gui.py` you will have to press "START SERVER" manually each time. If you prefer the server to start directly without an interface, you can use `server.py` by adding arguments in the console)*

Console arguments:

| Argument | Meaning |
| -------------------- | -------------------- |
| -h, --help | show help message and exit |
| -s, --setup | Run camera setup utility |
| -c, --camera CAMERA | Camera index |
| --width WIDTH | Stream width in pixels |
| --height HEIGHT | Stream height in pixels |
| --fps FPS | Stream frames per second |
| -a, --audio-device | Audio input device index (default: system default) |
| -r, --record | Enable recordings |
| -m, --motion | Enable motion detection |
| -p, --port PORT | Flask server port |
| --password PWD | Password to protect the web interface (leave empty- to disable) |

---

## 8. Advanced Settings

Thanks to the new graphical interface (`gui.py`), most settings are configured from the Launcher:
- **Camera and Audio**: Detected automatically; you can select them from the dropdown list.
- **Resolution and FPS**: Adjustable in the "CAMERA" section.
- **Port and Password**: Modifiable in the "NETWORK" section.
- **Motion Detection and Recording**: Toggleable via checkboxes.

For additional internal options (motion sensitivity, recording duration, etc.), you can edit the constants at the top of `server.py`.

---

## 9. Troubleshooting

| Problem                         | Solution                                              |
|---------------------------------|-------------------------------------------------------|
| No image / no sound             | Change the camera or audio device in the Launcher     |
| Stream is very slow             | Lower `STREAM_FPS` to 10 and `STREAM_WIDTH` to 640    |
| Can't access from outside       | Verify port forwarding and Windows firewall           |
| Public IP changes               | Install DuckDNS (see section 5)                       |
| Error installing OpenCV         | Try `pip install opencv-python-headless`              |
| Server closes immediately       | Run with `pythonw server.py` to hide the window       |
