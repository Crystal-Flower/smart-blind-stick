"""
Smart Stick Dashboard - single file
Reads the REAL ultrasonic sensor through your NodeMCU (USB serial),
speaks what it detects, and shows it on a live web dashboard.

  - Buzzer stays on the Arduino (instant physical warning)
  - Laptop adds voice + dashboard ("Obstacle ahead, 45 centimeters.")

Install:  pip install pyserial
Run:      python smart_stick.py      -> http://localhost:8000
Note:     Close Arduino Serial Monitor first (it locks the COM port).
"""
import json, platform, re, subprocess, threading, time, webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ===== Settings =====
MODE = "serial"        # "serial" = NodeMCU (default) | "sim" = slider, no hardware
SERIAL_PORT = None     # None = auto-detect, or e.g. "COM5"
BAUD_RATE = 115200
HTTP_PORT = 8000
BUZZER_CM = 5.0        # must match THRESHOLD_CM in the Arduino sketch
CHANGE_CM = 5          # re-announce only if distance changed by this much
CLEAR_AFTER = 3        # consecutive "no obstacle" readings before resetting
SPEECH_RATE = 0        # Windows voice speed: -10 (slow) .. 10 (fast)

OS = platform.system()
lock = threading.Lock()
state = {
    "mode": MODE, "connected": MODE == "sim", "port": None,
    "distance": None, "sim_distance": 100.0, "sim_clear": True,
    "voice_enabled": True, "voice_range": 100,
    "history": deque(maxlen=200), "log": deque(maxlen=30),
}
speech_process = None
voice = {"last_spoken": None, "clear_count": 0, "last_hist": 0.0}


# ===== Voice =====
def speak(text):
    global speech_process
    if speech_process and speech_process.poll() is None:
        speech_process.terminate()
    print(f"[VOICE] {text}")
    try:
        if OS == "Windows":
            ps = ("Add-Type -AssemblyName System.Speech; "
                  "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                  f"$s.Rate = {SPEECH_RATE}; $s.Speak('{text}')")
            speech_process = subprocess.Popen(
                ["powershell", "-NoProfile", "-Command", ps],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        elif OS == "Darwin":
            speech_process = subprocess.Popen(["say", text])
        else:
            speech_process = subprocess.Popen(["espeak", text])
    except FileNotFoundError:
        print("(No speech engine found. On Linux: sudo apt install espeak)")
    with lock:
        state["log"].appendleft({"t": time.strftime("%H:%M:%S"), "text": text})


def sentence(cm):
    n = int(round(cm))
    unit = "centimeter" if n == 1 else "centimeters"
    if n <= BUZZER_CM:
        return f"Stop! Obstacle very close, {n} {unit}."
    return f"Obstacle ahead, {n} {unit}."


def handle_reading(d):
    """Called for every sensor reading (cm, or None for no echo)."""
    now = time.time()
    with lock:
        state["distance"] = d
        if now - voice["last_hist"] >= 0.1:
            state["history"].append((now, d))
            voice["last_hist"] = now
        voice_on, vrange = state["voice_enabled"], state["voice_range"]

    if d is None or d > vrange:
        voice["clear_count"] += 1
        if voice["clear_count"] >= CLEAR_AFTER:
            voice["last_spoken"] = None
        return
    voice["clear_count"] = 0
    last = voice["last_spoken"]
    if voice_on and (last is None or abs(d - last) >= CHANGE_CM):
        speak(sentence(d))
        voice["last_spoken"] = d


# ===== Serial (NodeMCU) =====
def find_port():
    from serial.tools import list_ports
    keys = ("CH340", "CH341", "CP210", "USB-SERIAL", "USB SERIAL", "SILICON LABS")
    for p in list_ports.comports():
        text = f"{p.description} {p.manufacturer or ''}".upper()
        if any(k in text for k in keys):
            return p.device
    return None


def parse_line(line):
    """('dist', cm) / ('none', None) / (None, None) for noise."""
    low = line.lower()
    if low.startswith("distance"):
        m = re.search(r"[-+]?\d+(\.\d+)?", line)
        if m:
            return "dist", float(m.group())
        if "no echo" in low:
            return "none", None
        return None, None
    if line == "NO_OBJECT":
        return "none", None
    if line.startswith("DISTANCE:"):
        try:
            return "dist", float(line.split(":", 1)[1])
        except ValueError:
            return None, None
    return None, None


def serial_worker():
    import serial
    from serial.tools import list_ports
    while True:
        port = SERIAL_PORT or find_port()
        if not port:
            with lock:
                state["connected"], state["port"] = False, None
            print("No NodeMCU found. Ports:",
                  [f"{p.device} ({p.description})" for p in list_ports.comports()])
            time.sleep(2)
            continue
        try:
            ser = serial.Serial(port, BAUD_RATE, timeout=1)
        except serial.SerialException as e:
            print(f"Could not open {port}: {e}\n(Close Arduino Serial Monitor.)")
            time.sleep(2)
            continue

        print(f"Connected to {port}")
        with lock:
            state["connected"], state["port"] = True, port
        try:
            while True:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                kind, d = parse_line(line)
                if kind is None:
                    continue
                handle_reading(d)
        except (serial.SerialException, OSError):
            print("Serial connection lost. Reconnecting...")
        finally:
            with lock:
                state["connected"], state["distance"] = False, None
            try:
                ser.close()
            except Exception:
                pass
            voice["last_spoken"] = None
            time.sleep(1)


# ===== Simulation (no hardware) =====
def sim_worker():
    while True:
        with lock:
            d = None if state["sim_clear"] else state["sim_distance"]
        handle_reading(d)
        time.sleep(0.1)


# ===== Dashboard =====
HTML = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Smart Stick Dashboard</title>
<style>
:root{--bg:#0f1420;--card:#182032;--text:#e8edf7;--mute:#8793ad;--ok:#2ecc71;--bad:#ff4d4d}
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,Segoe UI,Arial,sans-serif;background:var(--bg);color:var(--text);padding:20px}
h1{margin:0 0 16px;font-size:22px}
.grid{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));max-width:1100px;margin:auto}
.card{background:var(--card);border-radius:14px;padding:18px}
.card h2{margin:0 0 12px;font-size:13px;color:var(--mute);text-transform:uppercase;letter-spacing:.08em}
.big{font-size:84px;font-weight:700;line-height:1}
.big small{font-size:28px;color:var(--mute);font-weight:400}
.pill{display:inline-block;padding:6px 14px;border-radius:99px;font-weight:600;margin-top:12px}
.bar{height:16px;background:#0c111c;border-radius:8px;overflow:hidden;margin-top:18px}
.fill{height:100%;width:0;transition:width .15s,background .15s}
canvas{width:100%;height:200px;display:block}
.row{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:12px 0}
.dot{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:6px;background:var(--bad)}
.dot.on{background:var(--ok)}
#log{max-height:200px;overflow:auto;font-size:14px}
#log div{padding:6px 0;border-bottom:1px solid #243049}
#log span{color:var(--mute);margin-right:8px}
button{background:#2b6fff;color:#fff;border:0;border-radius:8px;padding:8px 16px;font-size:14px;cursor:pointer}
button.off{background:#444}
input[type=range]{width:170px}
.tag{font-size:12px;padding:3px 10px;border-radius:99px;background:#2b3a5c;color:#9fc0ff;vertical-align:middle}
</style></head><body>
<div class="grid">
 <div style="grid-column:1/-1"><h1>🦯 Smart Stick Dashboard <span id="mode" class="tag"></span></h1></div>

 <div class="card">
  <h2>Distance</h2>
  <div class="big"><span id="dist">--</span> <small>cm</small></div>
  <div id="status" class="pill" style="background:#333">Waiting…</div>
  <div id="buz" class="pill" style="background:#ff4d4d;margin-left:8px;display:none">🔔 BUZZER</div>
  <div class="bar"><div id="fill" class="fill"></div></div>
 </div>

 <div class="card">
  <h2>Controls</h2>
  <div class="row"><span><span id="dot" class="dot"></span><span id="conn">Disconnected</span></span>
   <span id="port" style="color:var(--mute)"></span></div>
  <div class="row"><span>Laptop voice</span><button id="voiceBtn">ON</button></div>
  <div class="row"><span>Announce within <b id="rv">100</b> cm</span>
   <input id="range" type="range" min="10" max="300" step="10" value="100"></div>
  <div id="simbox" style="display:none">
   <div class="row"><span>Simulated distance <b id="sv">100</b> cm</span>
    <input id="sim" type="range" min="2" max="200" step="1" value="100"></div>
   <div class="row"><span>No obstacle</span><button id="clearBtn">ON</button></div>
  </div>
  <div class="row" style="color:var(--mute);font-size:13px">Buzzer (on Arduino) beeps at ≤ <span id="bz">5</span> cm</div>
 </div>

 <div class="card" style="grid-column:1/-1">
  <h2>Last 20 seconds</h2><canvas id="chart" width="1000" height="200"></canvas>
 </div>
 <div class="card" style="grid-column:1/-1">
  <h2>Voice announcements</h2><div id="log"><div style="color:var(--mute)">Nothing spoken yet.</div></div>
 </div>
</div>
<script>
const BUZZER = __BUZZER__, $ = id => document.getElementById(id);
$('bz').textContent = BUZZER;
let voiceOn = true, simClear = true;
const post = cfg => fetch('/api/config',{method:'POST',body:JSON.stringify(cfg)});
$('voiceBtn').onclick = () => post({voice_enabled: !voiceOn});
$('clearBtn').onclick = () => post({sim_clear: !simClear});
$('range').oninput = e => { $('rv').textContent = e.target.value; post({voice_range:+e.target.value}); };
$('sim').oninput = e => { $('sv').textContent = e.target.value; post({sim_distance:+e.target.value, sim_clear:false}); };

function colorFor(d){
  if (d === null) return ['#2f3b55','Clear / no obstacle'];
  if (d <= BUZZER) return ['#ff4d4d','DANGER – very close'];
  if (d <= 30) return ['#f5a623','Close'];
  if (d <= 100) return ['#d4c93a','Obstacle ahead'];
  return ['#2ecc71','Clear'];
}
function drawChart(hist){
  const c=$('chart'), g=c.getContext('2d'); g.clearRect(0,0,c.width,c.height);
  const MAXD=200, now=Date.now()/1000, W=20, H=c.height;
  g.strokeStyle='#243049'; g.fillStyle='#8793ad'; g.font='12px sans-serif';
  [0,50,100,150,200].forEach(v=>{const y=H-20-(v/MAXD)*(H-30);
    g.beginPath();g.moveTo(35,y);g.lineTo(c.width,y);g.stroke();g.fillText(v,4,y+4);});
  const by=H-20-(BUZZER/MAXD)*(H-30);
  g.strokeStyle='#ff4d4d55';g.beginPath();g.moveTo(35,by);g.lineTo(c.width,by);g.stroke();
  g.strokeStyle='#4da3ff';g.lineWidth=2;g.beginPath();let pen=false;
  hist.forEach(([t,d])=>{const x=35+(1-(now-t)/W)*(c.width-35);
    if(d===null||x<35){pen=false;return;}
    const y=H-20-(Math.min(d,MAXD)/MAXD)*(H-30);
    pen?g.lineTo(x,y):g.moveTo(x,y);pen=true;});
  g.stroke();g.lineWidth=1;
}
async function tick(){
  try{
    const s = await (await fetch('/api/state')).json();
    voiceOn = s.voice_enabled; simClear = s.sim_clear;
    const sim = s.mode==='sim';
    $('mode').textContent = sim ? 'Simulated' : 'NodeMCU · live sensor';
    $('simbox').style.display = sim ? 'block' : 'none';
    $('dot').className = 'dot' + (s.connected ? ' on' : '');
    $('conn').textContent = s.connected ? 'Connected' : 'Waiting for NodeMCU…';
    $('port').textContent = s.port || '';
    $('voiceBtn').textContent = voiceOn?'ON':'OFF'; $('voiceBtn').className = voiceOn?'':'off';
    $('clearBtn').textContent = simClear?'ON':'OFF'; $('clearBtn').className = simClear?'':'off';
    if (document.activeElement!==$('range')){$('range').value=s.voice_range;$('rv').textContent=s.voice_range;}
    if (document.activeElement!==$('sim')){$('sim').value=s.sim_distance;$('sv').textContent=Math.round(s.sim_distance);}
    const d=s.distance;
    $('dist').textContent = d===null?'--':Math.round(d);
    const [col,label]= s.connected ? colorFor(d) : ['#333','Waiting for device…'];
    $('status').style.background=col;
    $('status').style.color=(col==='#d4c93a'||col==='#f5a623')?'#111':'#fff';
    $('status').textContent=label;
    $('fill').style.width = d===null?'0%':Math.max(3,100-Math.min(d,200)/2)+'%';
    $('fill').style.background=col;
    $('buz').style.display = (d!==null && d<=BUZZER)?'inline-block':'none';
    drawChart(s.history);
    if (s.log.length) $('log').innerHTML=s.log.map(l=>`<div><span>${l.t}</span>${l.text}</div>`).join('');
  }catch(e){ $('conn').textContent='Server offline'; }
}
setInterval(tick,150); tick();
</script></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, body, ctype):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api/state":
            with lock:
                s = {k: (list(v) if isinstance(v, deque) else v) for k, v in state.items()}
            self._send(200, json.dumps(s), "application/json")
        elif self.path in ("/", "/index.html"):
            self._send(200, HTML.replace("__BUZZER__", str(BUZZER_CM)), "text/html; charset=utf-8")
        else:
            self._send(404, "Not found", "text/plain")

    def do_POST(self):
        if self.path != "/api/config":
            return self._send(404, "Not found", "text/plain")
        n = int(self.headers.get("Content-Length", 0))
        try:
            cfg = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            cfg = {}
        with lock:
            if "voice_enabled" in cfg: state["voice_enabled"] = bool(cfg["voice_enabled"])
            if "voice_range" in cfg: state["voice_range"] = max(10, min(400, int(cfg["voice_range"])))
            if "sim_distance" in cfg: state["sim_distance"] = max(2.0, min(200.0, float(cfg["sim_distance"])))
            if "sim_clear" in cfg: state["sim_clear"] = bool(cfg["sim_clear"])
        self._send(200, "{}", "application/json")


def main():
    if MODE == "serial":
        try:
            import serial  # noqa: F401
        except ImportError:
            print("pyserial missing. Run:  pip install pyserial")
            raise SystemExit(1)
        threading.Thread(target=serial_worker, daemon=True).start()
    else:
        threading.Thread(target=sim_worker, daemon=True).start()

    server = ThreadingHTTPServer(("127.0.0.1", HTTP_PORT), Handler)
    url = f"http://localhost:{HTTP_PORT}"
    print(f"Mode: {MODE}  |  Dashboard: {url}  (Ctrl+C to quit)")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
        if speech_process and speech_process.poll() is None:
            speech_process.terminate()


if __name__ == "__main__":
    main()
