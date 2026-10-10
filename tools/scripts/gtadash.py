#!/usr/bin/env python3
"""Live dashboard of GTA V on the Thor in the Mac's browser: frame graph (SurfaceFlinger present times, as the AoE
repo's fpsgraph.py), CPU/GPU clocks, GPU busy, temperature, memory, the game's busiest threads with the core they
run on, and FEX's counters (through the AoE agent, a memory peek every 10 s; needs AOE_REPO, see thor.py).

    gtadash.py [--port 8791] [--csv OUT]      then open http://127.0.0.1:8791

Cost on the Thor: one long-lived `adb shell` loop per data source, shell builtins plus one `cat` every 3 s; no
screen readback. Other scripts can mark the graph: curl -s 'http://127.0.0.1:8791/mark?label=pass%204'
The agent calls are serialized with a file lock in the AoE repo's agent.py, so a profiler can share the agent.
"""
import http.server
import json
import subprocess
import sys
import threading
import time
import urllib.parse

import thor

SERIAL = thor.SERIAL
LAYER_HINT = "SurfaceView[app.gamenative/"
EXE = "GTA5.exe"

lock = threading.Lock()
frames = []  # present times in ns
marks = []
last_seen = [0]
csv_file = None
sysrows = []  # {"t", "cpu0", "cpu3", "cpu7", "gpu", "busy", "temp", "avail"}
threads = {"t": 0, "pid": "", "rows": []}  # busiest threads over the last sample interval
fex = {"t": 0, "text": ""}
_prev_stat = {}


def adb_shell(cmd):
    return thor.sh(cmd)


def adb_popen(cmd):
    return subprocess.Popen(["adb", *(["-s", SERIAL] if SERIAL else []), "shell", cmd], stdout=subprocess.PIPE, text=True)


def game_layer():
    for line in adb_shell("dumpsys SurfaceFlinger --list").splitlines():
        if line.startswith(LAYER_HINT) and "(BLAST)" in line:
            return line.strip()
    return None


def device_now_ns():
    out = adb_shell("cat /proc/uptime").split()
    return int(float(out[0]) * 1e9) if out else 0


def add_window(text):
    vals = []
    for tok in text.split()[1:]:
        try:
            vals.append(int(tok))
        except ValueError:
            pass
    new = [vals[i + 1] for i in range(0, len(vals) - 2, 3) if 0 < vals[i + 1] < (1 << 62)]
    with lock:
        for t in new:
            if t > last_seen[0]:
                if csv_file and frames:
                    csv_file.write(f"{t},{(t - frames[-1]) / 1e6:.3f}\n")
                frames.append(t)
                last_seen[0] = t
        del frames[:-36000]
    if csv_file:
        csv_file.flush()


def frame_loop():
    while True:
        layer = game_layer()
        if not layer:
            time.sleep(3)
            continue
        cmd = f"while true; do dumpsys SurfaceFlinger --latency '{layer}'; echo ==END==; sleep 1; done"
        proc = adb_popen(cmd)
        buf, empty = [], 0
        for line in proc.stdout:
            if line.startswith("==END=="):
                text = "".join(buf)
                buf = []
                if len(text.split()) <= 1:
                    empty += 1
                    if empty >= 3:
                        break
                    continue
                empty = 0
                add_window(text)
            else:
                buf.append(line)
        proc.kill()
        time.sleep(1)


def game_pid():
    for l in adb_shell("ps -A -o PID,NAME").splitlines():
        if l.rstrip().endswith(EXE):
            return l.split()[0]
    return ""


SYS_CMD = ("read a < /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq; read b < /sys/devices/system/cpu/cpu3/cpufreq/scaling_cur_freq; "
           "read c < /sys/devices/system/cpu/cpu7/cpufreq/scaling_cur_freq; read g < /sys/class/kgsl/kgsl-3d0/gpuclk; "
           "read u < /sys/class/kgsl/kgsl-3d0/gpu_busy_percentage; read t < /sys/class/thermal/thermal_zone0/temp; "
           "while read k v x; do [ \"$k\" = MemAvailable: ] && m=$v; done < /proc/meminfo; "
           "echo SYS $a $b $c $g ${u%\\%*} $t $m")


def sys_loop():
    global _prev_stat
    while True:
        pid = game_pid()
        cat = f"cat /proc/{pid}/task/*/stat 2>/dev/null" if pid else "true"
        cmd = f"while true; do {SYS_CMD}; {cat}; echo ==END==; sleep 3; done"
        proc = adb_popen(cmd)
        buf, no_tasks, t_last = [], 0, time.time()
        for line in proc.stdout:
            if not line.startswith("==END=="):
                buf.append(line)
                continue
            now = time.time()
            row = {"t": now}
            stats = {}
            for l in buf:
                if l.startswith("SYS "):
                    p = l.split()
                    if len(p) >= 8 and all(x.strip().isdigit() for x in p[1:8]):
                        row.update(cpu0=int(p[1]) // 1000, cpu3=int(p[2]) // 1000, cpu7=int(p[3]) // 1000,
                                   gpu=int(p[4]) // 1000000, busy=int(p[5]), temp=int(p[6]) / 1000, avail=int(p[7]) // 1024)
                elif ")" in l:
                    head, rest = l.split(")", 1)
                    f = rest.split()
                    if len(f) > 36:
                        stats[head.split()[0]] = ((int(f[11]) + int(f[12])) * 10, int(f[36]), head.split("(", 1)[-1])
            buf = []
            with lock:
                if "cpu0" in row:
                    sysrows.append(row)
                    del sysrows[:-1200]
                if stats:
                    dt = now - t_last
                    rows = []
                    for tid, (ms, core, name) in stats.items():
                        if tid in _prev_stat:
                            rows.append({"tid": tid, "pct": (ms - _prev_stat[tid][0]) / dt / 10, "core": core, "name": name})
                    rows.sort(key=lambda r: -r["pct"])
                    threads.update(t=now, pid=pid, rows=rows[:10], n=len(stats))
                    _prev_stat = stats
                    t_last = now
                    no_tasks = 0
                else:
                    no_tasks += 1
                    _prev_stat = {}
            if no_tasks >= 3 and pid:  # the game is gone or restarted
                break
            if not pid and no_tasks >= 5:  # look for the game again
                break
            if not pid:
                no_tasks += 1
        proc.kill()
        time.sleep(2)


def fex_loop():
    """FEX counters through the AoE agent every 10 s (RVAs for the aoe4-perf6-30 build, see gfex.py)."""
    import struct
    try:
        import agent
    except ImportError:
        with lock:
            fex.update(t=time.time(), text="(no FEX counters: set AOE_REPO to the ageofempires-android checkout)")
        return
    BLOCKS = {"SmcHide": (0x3EF2C0, b"SMCHIDE1", ["qry", "qcorr", "prot", "pcorr"]),
              "FastTrap": (0x3EF328, b"FASTTRP1", ["taken", "fallback", "ill", "trap", "segv"]),
              "FastContinue": (0x3EF358, b"FSTCONT1", ["fast", "slow"])}
    prev, tprev = None, 0
    while True:
        time.sleep(10)
        if not threads["pid"]:
            continue
        try:
            if not agent.running():
                agent.start()
                agent.call(f"target {EXE}")
            cur = {}
            for name, (rva, marker, fields) in BLOCKS.items():
                data = agent.peek("libarm64ecfex.dll", rva, 8 * (1 + len(fields)))
                if data[:8] == marker:
                    cur[name] = dict(zip(fields, struct.unpack_from(f"<{len(fields)}Q", data, 8)))
            now = time.time()
            if prev and cur:
                parts = []
                for name in cur:
                    parts.append(name + ": " + " ".join(f"{k} {(cur[name][k] - prev[name][k]) / (now - tprev):.0f}/s" for k in cur[name] if name in prev))
                with lock:
                    fex.update(t=now, text=" | ".join(parts))
            prev, tprev = cur, now
        except Exception as e:  # the agent is not there, or the game restarted
            with lock:
                fex.update(t=time.time(), text=f"(no FEX counters: {str(e)[:60]})")
            prev = None


PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>GTA V on Thor</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{--bg:#101214;--fg:#e8e8e8;--dim:#8a9099;--grid:#2a2f36}
body{margin:0;background:var(--bg);color:var(--fg);font:13px ui-monospace,Menlo,monospace}
#top{display:flex;flex-wrap:wrap;gap:16px;padding:8px 16px;align-items:baseline}
.v{font-size:20px;font-weight:600}.l{color:var(--dim);font-size:11px}
canvas{display:block;width:100%}
#c{height:38vh}#s{height:22vh}
#bar,#fex{padding:3px 16px;color:var(--dim);font-size:11px}
table{border-collapse:collapse;margin:4px 16px}td,th{padding:1px 8px;text-align:right;font-size:12px}th{color:var(--dim);font-weight:normal}
td:first-child,th:first-child{text-align:left}
button{background:#22272e;color:var(--fg);border:1px solid #3a414b;border-radius:4px;padding:3px 10px;font:inherit}
.little{color:#c23a33}.big{color:#a0c4ff}.prime{color:#7ee787}
</style></head><body>
<div id="top">
 <div><div class="v" id="fps1">-</div><div class="l">FPS (1 s)</div></div>
 <div><div class="v" id="fps10">-</div><div class="l">FPS (10 s)</div></div>
 <div><div class="v" id="low">-</div><div class="l">1% low (30 s)</div></div>
 <div><div class="v" id="med">-</div><div class="l">median ms (30 s)</div></div>
 <div><div class="v" id="s50">-</div><div class="l">&gt;50 ms (30 s)</div></div>
 <div><div class="v" id="gpu">-</div><div class="l">GPU MHz / busy</div></div>
 <div><div class="v" id="cpu">-</div><div class="l">cpu0 / cpu3 / cpu7 MHz</div></div>
 <div><div class="v" id="temp">-</div><div class="l">°C zone0</div></div>
 <div><div class="v" id="mem">-</div><div class="l">MemAvailable MB</div></div>
 <div><button id="pause">pause</button> <button id="zoom">scale 100 ms</button></div>
</div>
<canvas id="c"></canvas>
<div id="bar">bar = one frame (green &le; 34 ms, yellow &le; 50, red &gt; 50); blue = FPS over 30 frames. Below: GPU MHz (orange, 0-700), GPU busy % (white), cpu7 MHz (blue, 0-3200) over the last 10 min.</div>
<canvas id="s"></canvas>
<table id="th"><thead><tr><th>thread</th><th>% of a core</th><th>core</th></tr></thead><tbody></tbody></table>
<div id="fex">-</div>
<script>
let frames=[],marks=[],sys=[],th={},fexText='',paused=false,scale=100,since=0;
const c=document.getElementById('c'),g=c.getContext('2d'),s=document.getElementById('s'),sg=s.getContext('2d');
document.getElementById('pause').onclick=e=>{paused=!paused;e.target.textContent=paused?'resume':'pause'};
document.getElementById('zoom').onclick=e=>{scale=scale==100?200:scale==200?500:100;e.target.textContent='scale '+scale+' ms'};
async function pull(){
 try{const r=await fetch('/data?since='+since);const j=await r.json();
  if(j.frames.length){frames=frames.concat(j.frames);since=j.frames[j.frames.length-1];if(frames.length>40000)frames=frames.slice(-40000)}
  marks=j.marks;sys=j.sys;th=j.threads;fexText=j.fex}catch(e){}
 setTimeout(pull,1000)}
const set=(id,v)=>document.getElementById(id).textContent=v;
function stats(){
 const n=frames.length;if(n>=3){const last=frames[n-1];
  const win=w=>{let i=n-1;while(i>0&&last-frames[i-1]<=w*1e9)i--;return i};
  const i1=win(1),i10=win(10),i30=win(30);
  set('fps1',((n-1-i1)/((last-frames[i1])/1e9||1)).toFixed(1));
  set('fps10',((n-1-i10)/((last-frames[i10])/1e9||1)).toFixed(1));
  const ft=[];for(let i=i30+1;i<n;i++)ft.push((frames[i]-frames[i-1])/1e6);
  const q=ft.slice().sort((a,b)=>a-b);const p99=q[Math.max(0,Math.floor(q.length*0.99)-1)];
  set('low',(1000/p99).toFixed(1));set('med',q[Math.floor(q.length/2)].toFixed(1));set('s50',ft.filter(f=>f>50).length)}
 if(sys.length){const r=sys[sys.length-1];set('gpu',r.gpu+' / '+r.busy+'%');set('cpu',r.cpu0+' / '+r.cpu3+' / '+r.cpu7);set('temp',r.temp.toFixed(1));set('mem',r.avail)}
 const tb=document.querySelector('#th tbody');tb.innerHTML='';
 for(const r of (th.rows||[])){const cls=r.core<3?'little':r.core<7?'big':'prime';
  tb.innerHTML+=`<tr><td>${r.tid} ${r.name||''}</td><td>${r.pct.toFixed(1)}</td><td class="${cls}">cpu${r.core}</td></tr>`}
 document.getElementById('fex').textContent=(th.n?th.n+' threads of pid '+th.pid+'. ':'no game process. ')+(fexText||'')}
function drawSys(){
 const W=s.clientWidth,H=s.clientHeight,dpr=window.devicePixelRatio||1;
 if(s.width!=W*dpr||s.height!=H*dpr){s.width=W*dpr;s.height=H*dpr}
 sg.setTransform(dpr,0,0,dpr,0,0);sg.clearRect(0,0,W,H);if(!sys.length)return;
 const t1=sys[sys.length-1].t,t0=t1-600,x=t=>40+(t-t0)/600*(W-44);
 const line=(key,max,col)=>{sg.strokeStyle=col;sg.beginPath();let f=true;for(const r of sys){if(r.t<t0)continue;const y=H-4-Math.min(r[key],max)/max*(H-8);if(f){sg.moveTo(x(r.t),y);f=false}else sg.lineTo(x(r.t),y)}sg.stroke()};
 sg.strokeStyle='#2a2f36';for(const fr of [0.25,0.5,0.75]){sg.beginPath();sg.moveTo(40,H-4-fr*(H-8));sg.lineTo(W,H-4-fr*(H-8));sg.stroke()}
 line('gpu',700,'#e3a04a');line('busy',100,'#e8e8e8');line('cpu7',3200,'#58a6ff');
 sg.fillStyle='#8a9099';sg.font='11px ui-monospace,Menlo,monospace';sg.fillText('10 min',2,12)}
function draw(){
 requestAnimationFrame(draw);if(paused)return;
 const W=c.clientWidth,H=c.clientHeight,dpr=window.devicePixelRatio||1;
 if(c.width!=W*dpr||c.height!=H*dpr){c.width=W*dpr;c.height=H*dpr}
 g.setTransform(dpr,0,0,dpr,0,0);g.clearRect(0,0,W,H);
 const bw=3,count=Math.floor((W-50)/bw),n=frames.length,y=ms=>H-6-Math.min(ms,scale)/scale*(H-12);
 g.font='11px ui-monospace,Menlo,monospace';
 for(const [ms,lab] of [[8.3,'120'],[11.1,'90'],[16.7,'60'],[22.2,'45'],[33.3,'30'],[50,'20'],[100,'10'],[200,'5']]){if(ms>scale)continue;
  g.strokeStyle='#2a2f36';g.beginPath();g.moveTo(40,y(ms));g.lineTo(W,y(ms));g.stroke();g.fillStyle='#8a9099';g.fillText(lab+' fps',2,y(ms)+4)}
 const start=Math.max(1,n-count);
 for(let i=start;i<n;i++){const ms=(frames[i]-frames[i-1])/1e6,x=W-(n-i)*bw;g.fillStyle=ms<=34?'#2d7a3a':ms<=50?'#a0741a':'#c23a33';g.fillRect(x,y(ms),bw-1,H-6-y(ms))}
 g.strokeStyle='#58a6ff';g.lineWidth=2;g.beginPath();let first=true;
 for(let i=Math.max(start,31);i<n;i++){const ms=(frames[i]-frames[i-30])/30/1e6,x=W-(n-i)*bw+1;if(first){g.moveTo(x,y(ms));first=false}else g.lineTo(x,y(ms))}
 g.stroke();g.lineWidth=1;
 if(n>1){for(const [t,label] of marks){let i=n-1;while(i>start&&frames[i]>t)i--;if(i<=start)continue;const x=W-(n-i)*bw;g.strokeStyle='#58a6ff';g.beginPath();g.moveTo(x,0);g.lineTo(x,H);g.stroke();g.fillStyle='#58a6ff';g.fillText(label,x+3,12)}}
 drawSys();stats()}
pull();draw();
</script></body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, body, ctype):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(url.query)
        if url.path == "/":
            self.send(200, PAGE, "text/html; charset=utf-8")
        elif url.path == "/data":
            since = int(q.get("since", ["0"])[0])
            with lock:
                body = json.dumps({"frames": [t for t in frames[-4000:] if t > since], "marks": list(marks[-50:]),
                                   "sys": sysrows[-200:], "threads": threads, "fex": fex["text"]})
            self.send(200, body, "application/json")
        elif url.path == "/mark":
            label = q.get("label", ["mark"])[0][:40]
            t = device_now_ns()
            with lock:
                marks.append((t, label))
            self.send(200, "ok\n", "text/plain")
        else:
            self.send(404, "not found\n", "text/plain")


def main():
    global csv_file
    args = sys.argv[1:]
    port = int(args[args.index("--port") + 1]) if "--port" in args else 8791
    if "--csv" in args:
        csv_file = open(args[args.index("--csv") + 1], "w")
        csv_file.write("present_ns,frame_ms\n")
    for fn in (frame_loop, sys_loop, fex_loop):
        threading.Thread(target=fn, daemon=True).start()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"dashboard at http://127.0.0.1:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
