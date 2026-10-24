import { test } from "node:test";
import assert from "node:assert/strict";
import type { AddressInfo } from "node:net";
import { HMEM } from "../index.ts";
import { CareMemory } from "../care.ts";
import { createServer } from "../server.ts";

const U = "alice-user-0001";

async function withServer(token: string, fn: (call: (p: string, body?: unknown, headers?: Record<string, string>) => Promise<{ status: number; json: any }>) => Promise<void>) {
  const server = createServer(new CareMemory(new HMEM()), token);
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
  const base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
  const call = async (p: string, body?: unknown, headers: Record<string, string> = {}) => {
    const res = await fetch(base + p, body === undefined ? { headers } : { method: "POST", headers: { "Content-Type": "application/json", ...headers }, body: typeof body === "string" ? body : JSON.stringify(body) });
    return { status: res.status, json: await res.json() };
  };
  try { await fn(call); } finally { server.close(); }
}

test("full flow over HTTP: remember, recall, feedback, export, forget", async () => {
  await withServer("", async (call) => {
    assert.equal((await call("/health")).json.ok, true);
    const w = await call("/remember", { user_id: U, content: "Evening walks help with feeling anxious before bed" });
    assert.equal(w.status, 201);
    const r = await call("/recall", { user_id: U, query: "I feel anxious at night" });
    assert.equal(r.status, 200); assert.equal(r.json.memories[0].id, w.json.id);
    assert.equal((await call("/feedback", { user_id: U, memory_id: w.json.id, kind: "helpful" })).status, 200);
    assert.equal((await call("/export", { user_id: U })).json.memories.length, 1);
    assert.equal((await call("/forget", { user_id: U })).json.erased, 1);
    assert.equal((await call("/recall", { user_id: U, query: "anxious at night" })).json.memories.length, 0);
  });
});

test("errors: policy 422, bad JSON 400, unknown route 404, oversized 413", async () => {
  await withServer("", async (call) => {
    assert.equal((await call("/remember", { user_id: U, content: "mail me at a@b.co please" })).json.error, "pii_suspected");
    assert.equal((await call("/remember", { user_id: U, content: "mail me at a@b.co please" })).status, 422);
    assert.equal((await call("/remember", "{not json")).status, 400);
    assert.equal((await call("/nope", {})).status, 404);
    assert.equal((await call("/remember", { user_id: U, content: "x".repeat(40000) })).status, 413);
  });
});

test("optional bearer token is enforced", async () => {
  await withServer("s3cret", async (call) => {
    assert.equal((await call("/health")).status, 401);
    assert.equal((await call("/health", undefined, { Authorization: "Bearer s3cret" })).status, 200);
  });
});
