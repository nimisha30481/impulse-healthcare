// DoseWISE dev supervisor. Keeps the servers up and restarts them if they stop.
//   node scripts/dev.mjs all      -> backend :8000 + frontend :5173
//   node scripts/dev.mjs backend  -> backend :8000 only
// If a port is already served (e.g. by another copy of this script), it just watches and takes
// over when that server goes away, so two copies never clash.
import { spawn } from "node:child_process";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const mode = process.argv[2] ?? "all";
const isWin = process.platform === "win32";
const children = new Set();

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

function supervise(name) {
  const cfg = SERVERS[name];
  let child = null;
  const check = async () => {
    if (!child && !(await listening(cfg.port))) {
      console.log(`[dev] starting ${name} on :${cfg.port}`);
      child = spawn(cfg.cmd, cfg.args, { cwd: root, stdio: "inherit", shell: cfg.shell });
      children.add(child);
      child.on("exit", (code) => {
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

supervise("backend");
if (mode === "all") supervise("frontend");
