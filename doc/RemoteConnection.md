How to solve remote connection problems:

## Why STUN fails remotely

STUN only helps peers **discover their public IP/port**. It works when at least one side is on a non-symmetric NAT (typical home router). When both sides are behind **symmetric NAT** (common in corporate networks, mobile data, etc.), the discovered candidates are useless — the ICE negotiation stalls in `checking`, exactly what you're probably seeing.

---

## Options

### Option 1 — Host a TURN Server ✅ Best for low latency + audio

TURN relays all media through a server you control. It's the only universal fix for NAT traversal.

| | |
|---|---|
| **Latency** | Adds ~20–80 ms (relay hop) — still much better than MJPEG |
| **Audio** | ✅ Full WebRTC audio preserved |
| **Cost** | Bandwidth: ~0.5–2 Mbps per viewer for 720p |
| **Software** | [coturn](https://github.com/coturn/coturn) — open source, runs on any Linux VPS |

A basic VPS (€3–5/month, e.g. Hetzner CX11) is enough for a single-viewer surveillance setup. Setup is ~30 minutes.

**Minimal coturn config:**
```ini
# /etc/turnserver.conf
listening-port=3478
tls-listening-port=5349
fingerprint
use-auth-secret
static-auth-secret=YOUR_SECRET
realm=yourdomain.com
cert=/etc/letsencrypt/live/yourdomain.com/fullchain.pem
pkey=/etc/letsencrypt/live/yourdomain.com/privkey.pem
```

And in your `index.html` (line 625):
```js
const pc = new RTCPeerConnection({
    iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        {
            urls: 'turn:yourdomain.com:3478',
            username: 'your_turn_user',
            credential: 'your_turn_password'
        }
    ]
});
```

---

### Option 2 — Free TURN services ⚠️ Not for production

Services like [Metered.ca](https://www.metered.ca/turn-server) or [Xirsys](https://xirsys.com/) offer free tiers. Drawbacks: bandwidth caps, privacy concerns (all your camera video passes through their servers), and unreliable uptime.

---

### Option 3 — Expose the server directly (port forwarding + no relay) 🚀 Zero added latency

If you control your home router, you can do **port forwarding** to your camera server. The client connects directly without NAT issues at all:

- Forward TCP/UDP port `8090` on your router to the machine running the server
- WebRTC peers use your **public IP** directly as a host candidate — no TURN/STUN needed
- You already have HTTPS support in the server (`--ssl-cert`/`--ssl-key`), which **you'll need for WebRTC on remote browsers**

> [!IMPORTANT]
> Direct port forwarding exposes your server to the internet. Make sure you use `--password` and `--ssl-cert` when running this way.

---

### Option 4 — Tunnel services (Tailscale / Cloudflare Tunnel) ✅ Easiest, no open ports

These create a private overlay network or secure tunnel — no port forwarding, no TURN server needed.

| Tool | How it works | Latency impact |
|---|---|---|
| **Tailscale** | WireGuard mesh VPN — devices act as if on the same LAN | Minimal (~5 ms) |
| **Cloudflare Tunnel** | Routes HTTP/HTTPS through Cloudflare edge | ~30–60 ms |

**Tailscale** is the best option here for your use case:
1. Install on both the server machine and your phone/laptop
2. Access the server via its Tailscale IP (`http://100.x.x.x:8090`) from anywhere
3. WebRTC sees a LAN-like connection → ICE finds host candidates immediately → **no STUN/TURN needed**

---

## Recommendation

| Scenario | Best option |
|---|---|
| You control your router | **Port forwarding** (zero latency penalty) |
| You want the simplest remote access | **Tailscale** (free, no config) |
| You need universal access (corporate/mobile NAT) | **coturn on a cheap VPS** |
| You need it now, just testing | **Metered.ca free TURN** (temporary only) |

For a personal home surveillance system, **Tailscale** is probably the sweet spot — free, ~5 minute setup, zero ongoing cost, and WebRTC works perfectly through it because it creates a virtual LAN between devices.

## Port Forwarding Details

If you want to go for option 3, Port Forwarding, **you must use HTTPS**. For this to work you must use the GUI to select your certificate and key files. If you use the server directly you have to use the `--ssl-cert` and `--ssl-key` arguments to the server:

```powershell
remotecameraserver --ssl-cert \path\to\cert.pem --ssl-key \path\to\key.pem --password "yourpassword"
# OR
python -m RemoteCameraMonitoring.server --ssl-cert \path\to\cert.pem --ssl-key \path\to\key.pem --password "yourpassword"
```

To secure your connection for WebRTC, you have three options:

### 1. Automatic HTTPS with Caddy (Recommended & Easiest)
Caddy acts as a secure reverse proxy directly in front of the Flask application, automating SSL/TLS certificate creation and handling the secure context completely in the background without needing any external tools.

* **How it works:**
  1. Download the `caddy.exe` binary for your platform from the [official Caddy downloads](https://caddyserver.com/download).
  2. Put `caddy.exe` in the project's `resources/` folder (`D:\Code\RemoteCameraMonitoring\resources\caddy.exe`).
  3. In the GUI launcher (`gui.py`), simply check **Enable HTTPS with Caddy** and start the server.
  4. The application automatically generates a `Caddyfile` mapping your local host and network IP, starts Caddy, and forwards secure traffic back to Flask.
* **Access URL:** Access your secure server at `https://localhost` (locally) or `https://<local-network-ip>` (remotely over your home network).
* **Certificate trust:** Caddy uses its own internal certificate authority. Browsers will show a warning on first load, which is expected and completely safe to bypass by clicking "Advanced" and "Proceed".

### 2. Generate your own certificate manually:

```bash
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes
```

Then access the server at `https://localhost:8090` (accept the browser warning for self-signed certs).

### 3. Let's Encrypt (free, trusted cert, for custom domains):

If you have a DDNS hostname, you can get a free certificate from Let's Encrypt using Certbot:

```bash
# On Windows, use the Certbot Windows installer from https://certbot.eff.org/
# Then run (requires port 80 forwarded on your router temporarily):
certbot certonly --standalone -d mycam.ddns.net
```

This produces:
- `C:\Certbot\live\mycam.ddns.net\fullchain.pem`
- `C:\Certbot\live\mycam.ddns.net\privkey.pem`

> [!NOTE]
> Certbot needs port **80** open briefly for the HTTP-01 challenge. You can close it again afterwards. Renew every 90 days with `certbot renew`.

Then launch the server and select the certificate files manually in the GUI, or start the headless server as:
```powershell
remotecameraserver --ssl-cert C:\Certbot\live\mycam.ddns.net\fullchain.pem --ssl-key C:\Certbot\live\mycam.ddns.net\privkey.pem --password "yourpassword"
```

## IMPORTANT

Port 8090 only carries the **signaling** (HTTP). The actual video/audio flows over **separate UDP ports** that aiortc picks dynamically (~49152–65535 range). Whether this works without forwarding those ports depends on your NAT type:

| NAT type | Works without UDP forwarding? |
|---|---|
| Full-cone / Port-restricted (most home routers) | ✅ Yes — STUN discovers a working mapping |
| Symmetric NAT (some ISPs/enterprise) | ❌ No — needs TURN |

**To test:** try connecting remotely. If the stream loads → your NAT is fine. If ICE stays in `checking` → you need TURN (or forward a UDP range).

**Optional: forward a fixed UDP port range** for guaranteed reliability:

1. In your router, forward **UDP 49152–49200** → your camera PC's local IP
2. Configure aiortc in `server.py` to only use those ports by adding after line 258:

```python
# Add after: _aiortc_loop = asyncio.new_event_loop()
import aioice
aioice.ice.ICE_POLICY_TCP_ONLY = False  # ensure UDP is used

# Restrict ICE to a known port range
os.environ.setdefault("AIORTC_ICE_PORT_RANGE", "49152-49200")
```

> [!NOTE]
> The `AIORTC_ICE_PORT_RANGE` env var isn't official — the reliable way is using `RTCConfiguration` with `iceCandidatePoolSize`. The simplest practical approach is just forwarding a /full/ UDP range (49152–65535) in your router if you see ICE failures.
