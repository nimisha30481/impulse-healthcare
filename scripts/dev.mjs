// DoseWISE dev supervisor. Keeps the servers up and restarts them if they stop.
//   node scripts/dev.mjs all      -> backend :8000 + frontend :5173
//   node scripts/dev.mjs backend  -> backend :8000 only
// Only one copy runs at a time (it holds 127.0.0.1:8799 as a lock; a second copy exits at once), so
// the Windows scheduled task "DoseWISE servers" can safely launch it every few minutes as a watchdog.
// If a port is already served by something else, it just watches and takes over when that goes away.
// Server output goes to logs/backend.log and logs/frontend.log.
import { spawn } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const mode = process.argv[2] ?? "all";
const isWin = process.platform === "win32";
const children = new Set();
const LOCK_PORT = 8799;
const logDir = path.join(root, "logs");

const SERVERS = {
  backend: {
    port: 8000,
    cmd: path.join(root, "backend", ".venv", isWin ? "Scripts/python.exe" : "bin/python"),
    args: ["-m", "uvicorn", "app.main:app", "--app-dir", path.join(root, "backend"), "--host", "127.0.0.1", "--port", "8000"],
    shell: false,
  },
  frontend: {
    port: 5173,
    cmd: "npm",
    args: ["--prefix", path.join(root, "frontend"), "run", "dev"],
    shell: isWin,
  },
};

const probe = (port, host) =>
  new Promise((resolve) => {
    const s = net.connect({ port, host });
    s.once("connect", () => { s.destroy(); resolve(true); });
    s.once("error", () => resolve(false));
  });
// Vite may listen on IPv6 (::1) only, uvicorn on IPv4 only: a port counts as busy if either answers.
const listening = async (port) => (await probe(port, "127.0.0.1")) || (await probe(port, "::1"));

function logFile(name) {
  fs.mkdirSync(logDir, { recursive: true });
  const file = path.join(logDir, `${name}.log`);
  try { if (fs.statSync(file).size > 5_000_000) fs.renameSync(file, `${file}.old`); } catch { /* new file */ }
  return fs.openSync(file, "a");
}

function supervise(name) {
  const cfg = SERVERS[name];
  let child = null;
  const check = async () => {
    if (!child && !(await listening(cfg.port))) {
      const out = logFile(name);
      fs.writeSync(out, `\n[dev] ${new Date().toISOString()} starting ${name} on :${cfg.port}\n`);
      console.log(`[dev] starting ${name} on :${cfg.port}`);
      child = spawn(cfg.cmd, cfg.args, { cwd: root, stdio: ["ignore", out, out], shell: cfg.shell, windowsHide: true });
      children.add(child);
      child.on("exit", (code) => {
        fs.writeSync(out, `[dev] ${new Date().toISOString()} ${name} exited (${code}); restarting\n`);
        fs.closeSync(out);
        console.log(`[dev] ${name} exited (${code}); restarting in 3 s`);
        children.delete(child);
        child = null;
      });
    }
  };
  check();
  setInterval(check, 3000);
}

function shutdown() {
  for (const c of children) c.kill();
  process.exit(0);
}
process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);

const lock = net.createServer();
lock.once("error", () => {
  console.log("[dev] already running; nothing to do");
  process.exit(0);
});
lock.listen(LOCK_PORT, "127.0.0.1", () => {
  supervise("backend");
  if (mode === "all") supervise("frontend");
});
