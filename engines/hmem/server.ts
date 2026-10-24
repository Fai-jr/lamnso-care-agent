// Local HTTP service around CareMemory. Binds to 127.0.0.1 only. Start:  npm run serve
//   POST /remember {user_id, content, source?, type?, tags?}
//   POST /recall   {user_id, query, top_n?, threshold?}
//   POST /feedback {user_id, memory_id, kind: helpful|not_helpful|wrong}
//   POST /export   {user_id}        POST /forget {user_id}        GET /health
// Optional shared secret: set HMEM_TOKEN and send "Authorization: Bearer <token>".

import http from "node:http";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { HMEM } from "./index.ts";
import { CareMemory, PolicyError } from "./care.ts";

const MAX_BODY = 16 * 1024;

function send(res: http.ServerResponse, status: number, body: unknown): void {
  const data = JSON.stringify(body);
  res.writeHead(status, { "Content-Type": "application/json", "Cache-Control": "no-store" });
  res.end(data);
}

function readJson(req: http.IncomingMessage): Promise<any> {
  return new Promise((resolve, reject) => {
    let size = 0;
    let tooLarge = false;
    const chunks: Buffer[] = [];
    req.on("data", (c: Buffer) => {
      size += c.length;
      if (size > MAX_BODY) { tooLarge = true; return; } // keep draining so the 413 reply can be delivered
      chunks.push(c);
    });
    req.on("end", () => {
      if (tooLarge) return reject(new PolicyError("body_too_large"));
      try { resolve(chunks.length ? JSON.parse(Buffer.concat(chunks).toString("utf-8")) : {}); }
      catch { reject(new PolicyError("invalid_json")); }
    });
    req.on("error", reject);
  });
}

export function createServer(care: CareMemory, token = ""): http.Server {
  return http.createServer(async (req, res) => {
    try {
      if (token && req.headers.authorization !== `Bearer ${token}`) return send(res, 401, { error: "unauthorized" });
      const url = (req.url ?? "").split("?")[0];
      if (req.method === "GET" && url === "/health") {
        return send(res, 200, { ok: true, engine: "h-mem", notes: care.hmem.store.all().length });
      }
      if (req.method !== "POST") return send(res, 404, { error: "not_found" });
      const b = await readJson(req);
      switch (url) {
        case "/remember": return send(res, 201, care.remember(b.user_id, b.content, { source: b.source, type: b.type, tags: b.tags }));
        case "/recall":   return send(res, 200, care.recall(b.user_id, b.query, { topN: b.top_n, threshold: b.threshold }));
        case "/feedback": return send(res, 200, care.feedback(b.user_id, b.memory_id, b.kind));
        case "/export":   return send(res, 200, { memories: care.exportFor(b.user_id) });
        case "/forget":   return send(res, 200, care.forget(b.user_id));
        default:          return send(res, 404, { error: "not_found" });
      }
    } catch (err) {
      if (err instanceof PolicyError) return send(res, err.code === "unauthorized" ? 401 : err.code === "body_too_large" ? 413 : err.code === "invalid_json" ? 400 : err.code === "not_found" ? 404 : 422, { error: err.code, message: err.message });
      console.error("hmem: unexpected error:", (err as Error).message); // never log request bodies
      return send(res, 500, { error: "internal_error" });
    }
  });
}

const entry = process.argv[1] ? pathToFileURL(path.resolve(process.argv[1])).href : "";
if (import.meta.url === entry) {
  const here = path.dirname(fileURLToPath(import.meta.url));
  const dataDir = process.env.HMEM_DATA_DIR ?? path.resolve(here, "..", "..", "data", "hmem");
  const port = Number(process.env.HMEM_PORT ?? 8765);
  const care = new CareMemory(new HMEM({ persistDir: dataDir, actor: "lamnso-care-agent" }));
  createServer(care, process.env.HMEM_TOKEN ?? "").listen(port, "127.0.0.1", () => {
    console.log(`H-MEM service on http://127.0.0.1:${port}  (data: ${dataDir})`);
  });
}
