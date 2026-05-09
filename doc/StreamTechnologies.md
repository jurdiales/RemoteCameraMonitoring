## Streaming Technologies Landscape

### 1. MJPEG over HTTP *(already implemented)*
Your current fallback. Sends a stream of JPEG frames as a multipart HTTP response.

| | |
|---|---|
| **Latency** | ~200–500 ms |
| **Audio** | ❌ No |
| **NAT/firewall** | ✅ Works anywhere (plain HTTP/HTTPS) |
| **Browser support** | ✅ Native `<img src="...">` |
| **Bandwidth** | High (no inter-frame compression) |

---

### 2. HLS — HTTP Live Streaming
Apple's protocol. The server chops video into small `.ts` segments and serves a `.m3u8` playlist file. The browser fetches segments sequentially over plain HTTP.

| | |
|---|---|
| **Latency** | 3–30 s (segment duration × buffer) — **not suitable for surveillance** |
| **Audio** | ✅ Yes (AAC/MP3) |
| **NAT/firewall** | ✅ Works anywhere (pure HTTP) |
| **Browser support** | ✅ Native on Safari; Chrome/Firefox need a JS lib (hls.js) |
| **Bandwidth** | Low (H.264 with temporal compression) |

HLS is designed for broadcast (Netflix-style). The inherent latency makes it a poor fit for live surveillance. Low-Latency HLS (LL-HLS) reduces it to ~1–2 s but requires a more complex server.

---

### 3. RTSP — Real-Time Streaming Protocol
The protocol used by IP cameras, NVRs, VLC, and FFmpeg. Runs over TCP/UDP, not HTTP.

| | |
|---|---|
| **Latency** | ~100–300 ms |
| **Audio** | ✅ Yes |
| **NAT/firewall** | ⚠️ Difficult — not HTTP, often blocked; needs port forwarding of a dedicated port |
| **Browser support** | ❌ No native browser support — needs VLC, a dedicated app, or a gateway |
| **Bandwidth** | Low (H.264/H.265) |

RTSP is great for LAN use (e.g., viewing in VLC or an NVR like Frigate/Home Assistant). For remote browser access it requires a bridge (e.g., WebRTC-to-RTSP gateway).

**Easy to add with OpenCV:**
```python
# OpenCV can write to an RTSP sink via FFmpeg backend:
# cap = cv2.VideoWriter("rtsp://localhost:8554/stream", ...)
# But you'd need mediamtx or a similar RTSP server running alongside
```

---

### 4. WebSockets + raw frames
Send JPEG frames over a WebSocket connection. Essentially MJPEG but over a persistent socket rather than HTTP chunked transfer.

| | |
|---|---|
| **Latency** | ~100–300 ms |
| **Audio** | ⚠️ Possible but complex (PCM chunks) |
| **NAT/firewall** | ✅ Works over HTTP/HTTPS upgrade |
| **Browser support** | ✅ Universal (JS WebSocket API) |
| **Bandwidth** | High (same as MJPEG, no temporal compression) |

Slightly lower latency than MJPEG and easier to add bi-directional control messages on the same connection. Implementable with Flask-SocketIO or aiohttp in ~50 lines.

---

### 5. RTMP — Real-Time Messaging Protocol
The protocol used by OBS to stream to Twitch/YouTube. Requires a dedicated RTMP server (nginx-rtmp, SRS, mediamtx).

| | |
|---|---|
| **Latency** | 1–5 s |
| **Audio** | ✅ Yes |
| **NAT/firewall** | ⚠️ Needs port 1935 forwarded |
| **Browser support** | ❌ No native browser support (Flash is dead) |

Not relevant for your use case.

---

### 6. FFmpeg → mediamtx (multi-protocol hub)
[mediamtx](https://github.com/bluenviron/mediamtx) (formerly rtsp-simple-server) is a lightweight Go binary that accepts a video source and re-publishes it simultaneously as RTSP, HLS, WebRTC, and RTMP. You pipe your OpenCV frames into it via FFmpeg.

```
OpenCV → FFmpeg (stdin pipe) → mediamtx → { RTSP / HLS / WebRTC / RTMP }
```

This is what production DIY NVR systems (Frigate, Agent DVR) do under the hood.

---

## Comparison Table

| Protocol | Latency | Audio | Browser native | Firewall friendly | Best for |
|---|---|---|---|---|---|
| **WebRTC** | < 100 ms | ✅ | ✅ | ⚠️ (NAT issues) | Real-time surveillance |
| **MJPEG** | 200–500 ms | ❌ | ✅ | ✅ | Fallback / simple |
| **WebSockets+JPEG** | 100–300 ms | ⚠️ | ✅ | ✅ | Better fallback |
| **HLS** | 3–30 s | ✅ | ⚠️ | ✅ | VOD / broadcast |
| **RTSP** | 100–300 ms | ✅ | ❌ | ⚠️ | LAN / NVR apps |
| **RTMP** | 1–5 s | ✅ | ❌ | ⚠️ | Platform streaming |

---

## What Would Actually Make Sense to Add

Given your setup (Python/Flask server, browser viewer, surveillance use case):

### Short-term — Replace MJPEG fallback with WebSocket frames
Keeps pure-HTTP simplicity but gets latency down to ~150 ms and gives you a path to add audio later. Implementable with Flask-SocketIO in ~30 lines server-side.

### Medium-term — Add RTSP output for LAN clients
Lets you view the camera in VLC, Home Assistant, or any NVR on your local network without going through the web interface. Best done via `mediamtx` as a sidecar process, with your server pushing frames to it via FFmpeg.

### Not worth it — HLS / RTMP
Too much latency or too little browser support for surveillance.

**For your remote access problem specifically**, WebRTC (your current approach) remains the right technology — the NAT/STUN issues are an infrastructure problem, not a technology limitation.