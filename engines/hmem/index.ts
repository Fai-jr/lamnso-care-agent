// H-MEM for the Lamnso Care Agent: the Meterless reference engine (Apache-2.0, see NOTICE) extended with the
// privacy controls a mental-health companion needs. The conformance suite runs against THIS class.
//
//  1. The audit ledger never stores a user's query text. The reference logs `details.query` on every read,
//     which would write the user's raw message to disk. We keep only a short digest and the length.
//  2. eraseUser() really erases: records are deleted, the content held in ledger snapshots is redacted
//     (the fact that a memory existed and was erased stays on the audit trail), and in-memory sleep
//     backups that could resurrect the data are dropped.

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { HMEM as ReferenceHMEM } from "./src/index.ts";
import type { HMEMOptions, LedgerEntry, MemoryRecord } from "./src/types.ts";

export * from "./src/types.ts";
export { embed, cosine, tokenize, jaccard } from "./src/embeddings.ts";

function digest(text: string): string {
  return crypto.createHash("sha256").update(text).digest("hex").slice(0, 10);
}

export class HMEM extends ReferenceHMEM {
  private readonly ledgerFile?: string;

  constructor(opts: HMEMOptions = {}) {
    super(opts);
    this.ledgerFile = opts.persistDir ? path.join(opts.persistDir, "ledger.jsonl") : undefined;

    // (1) never persist query text
    const ledger = this.ledger as unknown as { log: (...args: any[]) => LedgerEntry };
    const original = ledger.log.bind(this.ledger);
    ledger.log = (memoryId: string, action: string, actor: string, extra?: any) => {
      const q = extra?.details?.query;
      if (typeof q === "string") {
        const { query: _dropped, ...rest } = extra.details;
        extra = { ...extra, details: { ...rest, queryDigest: digest(q), queryChars: q.length } };
      }
      return original(memoryId, action, actor, extra);
    };
  }

  recordsFor(userId: string): MemoryRecord[] {
    return this.store.all().filter((m) => m.chatId === userId);
  }

  /** Erase everything stored for one user. Returns the number of memories erased. */
  eraseUser(userId: string): number {
    const mine = this.recordsFor(userId);
    const ids = new Set(mine.map((m) => m.id));
    for (const m of mine) this.store.delete(m.id, "user_erasure");

    // (2) redact content from the audit trail, keep the fact of existence + erasure
    const entries = this.ledger.all() as LedgerEntry[];
    for (const e of entries) {
      if (!ids.has(e.memoryId)) continue;
      if (e.previousState) e.previousState = { id: e.memoryId };
      if (e.newState) e.newState = { id: e.memoryId };
      e.details = { erased: true };
    }
    if (this.ledgerFile) {
      fs.writeFileSync(this.ledgerFile, entries.map((e) => JSON.stringify(e)).join("\n") + (entries.length ? "\n" : ""), "utf-8");
    }
    // sleep backups live in RAM and hold full copies of every record; drop them so nothing can be restored
    const backups = (this.sleep as unknown as { backups?: Map<string, unknown> }).backups;
    backups?.clear();
    return mine.length;
  }
}
