#!/usr/bin/env python3
"""Code Racer code server: compiles and runs short Python, C and Java programs.

POST /run     {"language": "py" | "c" | "java", "code": "..."}
              -> {"status", "signal", "compiler_error", "program_output",
                  "program_error", "timed_out", "time_ms"}   (Wandbox-shaped)
GET  /health  -> {"ok": true, "versions": {...}, "network_isolated": bool}

Only the Python standard library is used. Each job runs in its own temp
directory as the unprivileged "runner" user, with CPU, memory, file-size and
process limits, a wall-clock timeout and capped output.
"""
import collections
import json
import os
import pwd
import resource
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", "10000"))
ALLOWED_ORIGINS = {o.strip() for o in os.environ.get(
    "ALLOWED_ORIGINS", "https://code-racer.netlify.app").split(",") if o.strip()}
WALL_SECONDS = float(os.environ.get("WALL_SECONDS", "30"))
CPU_SECONDS = int(os.environ.get("CPU_SECONDS", "10"))
RATE_PER_MINUTE = int(os.environ.get("RATE_PER_MINUTE", "20"))
CONCURRENCY = int(os.environ.get("CONCURRENCY", "1"))
MAX_CODE = 20_000
MAX_OUTPUT = 64_000
MAX_FILE = 2_000_000

SLOTS = threading.BoundedSemaphore(CONCURRENCY)
IS_ROOT = os.geteuid() == 0
try:
    RUNNER = pwd.getpwnam("runner") if IS_ROOT else None
except KeyError:
    RUNNER = None


# ---------------------------------------------------------------- sandboxing
def limits(mem_bytes):
    """preexec_fn for every child: new session, resource limits, drop to runner."""
    def apply():
        os.setsid()
        resource.setrlimit(resource.RLIMIT_CPU, (CPU_SECONDS, CPU_SECONDS + 1))
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_FILE, MAX_FILE))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        if mem_bytes:
            try:
                resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
            except (ValueError, OSError):   # macOS refuses RLIMIT_AS; Linux (production) applies it
                pass
        if RUNNER:
            resource.setrlimit(resource.RLIMIT_NPROC, (128, 128))
            os.setgroups([])
            os.setgid(RUNNER.pw_gid)
            os.setuid(RUNNER.pw_uid)
    return apply


def detect_netns():
    """True if 'unshare -rn' works for the runner user, so code gets no network."""
    if not shutil.which("unshare"):
        return False
    try:
        r = subprocess.run(["unshare", "-rn", "true"], preexec_fn=limits(0),
                           capture_output=True, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


NETNS = detect_netns()


def run(cmd, cwd, mem_bytes, timeout):
    """Run one command in the sandbox. Returns (exit_code, stdout, stderr, timed_out)."""
    if NETNS:
        cmd = ["unshare", "-rn"] + cmd
    out_path, err_path = os.path.join(cwd, ".stdout"), os.path.join(cwd, ".stderr")
    with open(out_path, "wb") as out, open(err_path, "wb") as err:
        if RUNNER:
            for p in (out_path, err_path):
                os.chown(p, RUNNER.pw_uid, RUNNER.pw_gid)
        env = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"), "HOME": cwd, "LANG": "C.UTF-8",
               "PYTHONIOENCODING": "utf-8"}
        proc = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.DEVNULL, stdout=out,
                                stderr=err, env=env, preexec_fn=limits(mem_bytes))
        timed_out = False
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
    if RUNNER and CONCURRENCY == 1:
        subprocess.run(["pkill", "-KILL", "-u", "runner"], capture_output=True)

    def read(p):
        with open(p, "rb") as f:
            data = f.read(MAX_OUTPUT + 1)
        text = data[:MAX_OUTPUT].decode("utf-8", "replace")
        return text + ("\n[output truncated]" if len(data) > MAX_OUTPUT else "")
    return proc.returncode, read(out_path), read(err_path), timed_out


def job(language, code):
    started = time.monotonic()
    work = tempfile.mkdtemp(prefix="race-")
    if RUNNER:
        os.chown(work, RUNNER.pw_uid, RUNNER.pw_gid)
    res = {"status": "0", "signal": "", "compiler_error": "", "program_output": "",
           "program_error": "", "timed_out": False}

    def left():
        return max(1.0, WALL_SECONDS - (time.monotonic() - started))

    def write(name):
        path = os.path.join(work, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        if RUNNER:
            os.chown(path, RUNNER.pw_uid, RUNNER.pw_gid)

    try:
        if language == "py":
            write("main.py")
            code_, out, err, to = run(["python3", "-I", "-B", "main.py"], work, 512 << 20, left())
            if any(k in err for k in ("SyntaxError", "IndentationError", "TabError")):
                res["compiler_error"] = err
            else:
                res["program_output"], res["program_error"] = out, err
        elif language == "c":
            write("main.c")
            code_, out, err, to = run(["gcc", "-std=c17", "-O0", "-Wall", "-o", "main", "main.c", "-lm"],
                                      work, 1024 << 20, left())
            if code_ != 0 or to:
                res["compiler_error"] = err or "compilation failed"
            else:
                code_, out, err, to = run(["./main"], work, 256 << 20, left())
                res["program_output"], res["program_error"] = out, err
        elif language == "java":
            write("Main.java")
            # Single-file source launch: one JVM compiles in memory and runs. RLIMIT_AS is
            # left off because the JVM reserves far more address space than it uses.
            code_, out, err, to = run(["java", "-Xmx128m", "-Xss1m", "-XX:+UseSerialGC",
                                       "-XX:TieredStopAtLevel=1", "-Xshare:auto", "Main.java"],
                                      work, 0, left())
            if "error: compilation failed" in err:
                res["compiler_error"] = err
            else:
                res["program_output"], res["program_error"] = out, err
        else:
            return 400, {"error": "language must be py, c or java"}
        for k in ("compiler_error", "program_output", "program_error"):
            res[k] = res[k].replace(os.path.realpath(work) + os.sep, "").replace(work + os.sep, "")
        if code_ == -signal.SIGXCPU:
            to = True
        res["timed_out"] = to
        if to:
            res["status"], res["signal"] = "124", "Killed"
            res["program_error"] += "\nTime limit exceeded: the program ran too long (is there an endless loop?)."
        else:
            res["status"] = str(code_ if code_ >= 0 else 128 - code_)
            if code_ < 0:
                res["signal"] = signal.Signals(-code_).name
        res["time_ms"] = int((time.monotonic() - started) * 1000)
        return 200, res
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ---------------------------------------------------------------- versions
def first_line(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return (r.stdout or r.stderr).strip().splitlines()[0]
    except Exception:
        return "unavailable"


VERSIONS = {"py": first_line(["python3", "--version"]),
            "c": "gcc " + first_line(["gcc", "-dumpfullversion"]),
            "java": first_line(["java", "-version"])}


# ---------------------------------------------------------------- rate limiting
HITS = collections.defaultdict(collections.deque)
HITS_LOCK = threading.Lock()


def allowed(ip):
    now = time.monotonic()
    with HITS_LOCK:
        q = HITS[ip]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= RATE_PER_MINUTE:
            return False
        q.append(now)
        if len(HITS) > 10_000:
            HITS.clear()
        return True


# ---------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "CodeRacer/1"

    def cors(self):
        origin = self.headers.get("Origin", "")
        if "*" in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", "*")
        elif origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def reply(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_GET(self):
        if self.path.split("?")[0] in ("/", "/health"):
            return self.reply(200, {"ok": True, "versions": VERSIONS, "network_isolated": NETNS})
        self.reply(404, {"error": "not found"})

    def do_POST(self):
        if self.path.split("?")[0] != "/run":
            return self.reply(404, {"error": "not found"})
        ip = (self.headers.get("X-Forwarded-For") or self.client_address[0]).split(",")[0].strip()
        if not allowed(ip):
            return self.reply(429, {"error": f"Too many runs. The limit is {RATE_PER_MINUTE} per minute."})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > MAX_CODE * 2:
                return self.reply(413, {"error": "program too long"})
            body = json.loads(self.rfile.read(length) or b"{}")
            language, code = body.get("language"), body.get("code")
        except (ValueError, AttributeError):
            return self.reply(400, {"error": "send JSON: {\"language\": ..., \"code\": ...}"})
        if not isinstance(code, str) or not code.strip() or len(code) > MAX_CODE:
            return self.reply(400, {"error": f"code must be 1 to {MAX_CODE} characters"})
        if not SLOTS.acquire(timeout=WALL_SECONDS):
            return self.reply(503, {"error": "server busy, try again"})
        try:
            status, res = job(language, code)
        except Exception as e:
            print(f"job failed: {e!r}", flush=True)
            status, res = 500, {"error": "the code server hit an internal error"}
        finally:
            SLOTS.release()
        self.reply(status, res)

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} {fmt % args}", flush=True)


if __name__ == "__main__":
    print(f"Code Racer server on :{PORT}  versions={VERSIONS}  sandbox_user={'runner' if RUNNER else 'none'}  "
          f"network_isolated={NETNS}  origins={sorted(ALLOWED_ORIGINS)}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
