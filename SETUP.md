# AviarCam — Guía de Instalación y Configuración
## Sistema de vigilancia doméstico para mascotas

---

## 1. Requisitos previos

- **Python 3.9 o superior** — descarga en https://python.org  
  ⚠️ Durante la instalación marca la opción **"Add Python to PATH"**
- **Webcam** conectada al portátil (USB o integrada)
- Portátil **siempre encendido y conectado a la red** mientras quieras vigilar

---

## 2. Instalación de dependencias

Abre el **Símbolo del sistema (CMD)** o **PowerShell** y ejecuta:

```
cd C:\ruta\donde\guardaste\los\archivos
pip install -r requirements.txt
```

Si `pip` no se reconoce, prueba con:
```
python -m pip install -r requirements.txt
```

---

## 3. Arrancar el servidor

```
python server.py
```

Verás algo así:
```
=======================================================
  AviarCam — Sistema de Vigilancia Doméstico
=======================================================
  Cámara:       índice 0
  Resolución:   1280×720 @ 20fps
  Acceso local: http://localhost:8080
=======================================================
```

Abre **http://localhost:8080** en el navegador del mismo portátil para comprobar que funciona.

> **¿No se ve imagen?** Prueba a cambiar `CAMERA_INDEX = 0` por `CAMERA_INDEX = 1`
> en las primeras líneas de `server.py` y reinicia.

---

## 4. Acceso remoto mediante Port Forwarding

Esta es la parte más importante para ver la cámara desde fuera de casa.

### 4.1 Conoce la IP local del portátil

En CMD ejecuta:
```
ipconfig
```
Busca la línea **Dirección IPv4** bajo tu adaptador Wi-Fi o Ethernet.
Ejemplo: `192.168.1.105`

**Apunta esa IP** — la necesitarás en el paso 4.3.

### 4.2 Asigna IP fija al portátil (recomendado)

Para que la IP local no cambie tras cada reinicio del router:

1. Ve a **Configuración → Red e Internet → Wi-Fi → Propiedades de hardware**
2. Selecciona **Editar** en "Asignación de IP"
3. Cambia a **Manual** y activa IPv4
4. Introduce:
   - Dirección IP: `192.168.1.105` (la que anotaste arriba)
   - Máscara de subred: `255.255.255.0`
   - Puerta de enlace: IP de tu router (normalmente `192.168.1.1`)
   - DNS preferido: `8.8.8.8`

### 4.3 Configura el reenvío de puertos en tu router

La interfaz varía según el fabricante, pero el proceso es similar:

1. Abre un navegador y ve a la dirección de tu router:
   - Movistar/O2: `192.168.1.1`
   - Vodafone: `192.168.0.1`
   - Orange: `192.168.1.1`
2. Introduce usuario y contraseña (suelen estar en la pegatina del router)
3. Busca la sección: **"Port Forwarding"**, **"NAT"**, **"Virtual Servers"** o similar
4. Crea una nueva regla con estos datos:

   | Campo              | Valor                         |
   |--------------------|-------------------------------|
   | Nombre / Servicio  | `AviarCam`                    |
   | Protocolo          | `TCP`                         |
   | Puerto externo     | `8080`                        |
   | Puerto interno     | `8080`                        |
   | IP de destino      | `192.168.1.105` (la del portátil) |
   | Estado             | Habilitado / Activo           |

5. Guarda y reinicia el router si te lo pide.

### 4.4 Conoce tu IP pública

Ve a https://www.whatismyip.com — te mostrará tu IP pública.  
Ejemplo: `88.12.34.56`

⚠️ **Esta IP puede cambiar** si tu ISP usa IPs dinámicas (lo habitual).  
Consulta el apartado 5 para solucionarlo.

### 4.5 Accede desde fuera

Desde cualquier dispositivo con datos móviles o red diferente, abre:
```
http://88.12.34.56:8080
```

¡Ya puedes ver a tu canario y tu agapórni desde cualquier lugar!

---

## 5. IP dinámica — Configura un nombre de dominio gratuito (DDNS)

Si tu IP pública cambia, necesitas un servicio DDNS que te dé un nombre fijo.

### Opción recomendada: DuckDNS (gratis y sencillo)

1. Ve a https://www.duckdns.org y regístrate con Google o GitHub
2. Crea un subdominio, por ejemplo: `mis-pajaros.duckdns.org`
3. Descarga el **cliente Windows** desde la misma web para que actualice
   tu IP automáticamente en segundo plano
4. A partir de ahora accede con:
   ```
   http://mis-pajaros.duckdns.org:8080
   ```

---

## 6. Abrir el puerto en el Firewall de Windows

Si el acceso externo no funciona, puede que el firewall esté bloqueando:

1. Abre **Panel de control → Sistema y seguridad → Firewall de Windows Defender**
2. Haz clic en **Configuración avanzada**
3. **Reglas de entrada → Nueva regla**
4. Tipo: **Puerto** → TCP → Puerto específico: `8080`
5. Acción: **Permitir la conexión**
6. Aplica a: Dominio, Privado y Público
7. Nombre: `AviarCam`

---

## 7. Inicio automático con Windows

Para que el servidor arranque solo cuando enciendas el portátil:

1. Crea un archivo `iniciar_aviarcam.bat` con este contenido:
   ```batch
   @echo off
   cd /d C:\ruta\donde\guardaste\los\archivos
   python server.py
   ```
2. Pulsa `Win + R`, escribe `shell:startup` y presiona Enter
3. Copia (o crea un acceso directo de) `iniciar_aviarcam.bat` en esa carpeta

---

## 8. Ajustes avanzados en server.py

En las primeras líneas de `server.py` puedes personalizar:

| Variable             | Descripción                                         |
|----------------------|-----------------------------------------------------|
| `CAMERA_INDEX`       | 0 = primera webcam, 1 = segunda, etc.               |
| `STREAM_WIDTH/HEIGHT`| Resolución del stream                               |
| `STREAM_FPS`         | Fotogramas por segundo (baja a 10 si va lento)      |
| `MOTION_THRESHOLD`   | Sensibilidad de detección (sube para menos alertas) |
| `RECORD_SECONDS`     | Segundos de grabación tras detectar movimiento      |
| `MAX_RECORDINGS`     | Máximo de archivos antes de borrar los más viejos   |
| `FLASK_PORT`         | Puerto del servidor (defecto: 8080)                 |

---

## 9. Solución de problemas

| Problema                        | Solución                                              |
|---------------------------------|-------------------------------------------------------|
| No se ve imagen                 | Cambia `CAMERA_INDEX` a 1 o 2                         |
| Imagen muy lenta                | Baja `STREAM_FPS` a 10 y `STREAM_WIDTH` a 640         |
| No accedo desde fuera           | Verifica port forwarding y el firewall de Windows     |
| IP pública cambia               | Instala DuckDNS (ver apartado 5)                      |
| Error al instalar OpenCV        | Prueba `pip install opencv-python-headless`            |
| El servidor se cierra solo      | Ejecuta con `pythonw server.py` para que no muestre ventana |
