// Care policy layer on top of H-MEM. Everything the web service exposes goes through here, so the privacy
// rules hold no matter which client calls it.
//   * every read and write is bound to a pseudonymous user id (the reference lets chat-less records leak
//     across users; this layer never writes one and never returns one)
//   * only short notes are stored: length-limited, personal identifiers rejected, instruction-like text rejected
//   * duplicates are merged, and each user has a cap
//   * export and erase are first-class operations

import { HMEM } from "./index.ts";
import type { FeedbackKind, MemoryRecord, MemoryType } from "./index.ts";

export class PolicyError extends Error {
  constructor(readonly code: string, message?: string) {
    super(message ?? code);
  }
}

const USER_ID = /^[A-Za-z0-9_-]{8,64}$/;
const TYPES: MemoryType[] = ["personal", "factual", "preference", "general"];
const MIN_CHARS = 8;
const MAX_CHARS = 200;

const PII: RegExp[] = [
  /[\w.+-]+@[\w-]+\.[\w.-]+/,          // e-mail
  /https?:\/\/|www\./i,                 // links
  /(?:\+?\d[\s().-]?){7,}/,             // phone numbers, long digit runs, full dates
  /(^|\s)@\w{3,}/,                      // social handles
];
const INSTRUCTION_LIKE: RegExp[] = [
  /\b(ignore|disregard|override|forget)\b.{0,40}\b(instruction|prompt|rule|previous|above)/i,
  /system prompt/i,
  /\byou (are|must|should) now\b/i,
  /\bact as\b/i,
];

export interface CareOptions {
  maxPerUser?: number;
  topN?: number;
  threshold?: number;
}

export interface RecalledNote {
  id: string;
  content: string;
  score: number;
  type: MemoryType;
  layer: string;
  confidence: number;
  source: string;
}

export function validateUserId(userId: unknown): string {
  if (typeof userId !== "string" || !USER_ID.test(userId)) {
    throw new PolicyError("invalid_user", "user_id must be 8-64 characters: letters, digits, _ or -");
  }
  return userId;
}

export function checkContent(content: unknown): string {
  if (typeof content !== "string") throw new PolicyError("content_length");
  const text = content.trim().replace(/\s+/g, " ");
  if (text.length < MIN_CHARS || text.length > MAX_CHARS) throw new PolicyError("content_length", `notes must be ${MIN_CHARS}-${MAX_CHARS} characters`);
  if (PII.some((r) => r.test(text))) throw new PolicyError("pii_suspected", "note looks like it contains a personal identifier");
  if (INSTRUCTION_LIKE.some((r) => r.test(text))) throw new PolicyError("injection_suspected", "note looks like an instruction, not a memory");
  return text;
}

const normalise = (s: string) => s.toLowerCase().replace(/\s+/g, " ").trim();

export class CareMemory {
  readonly maxPerUser: number;
  readonly topN: number;
  readonly threshold: number;

  constructor(readonly hmem: HMEM, opts: CareOptions = {}) {
    this.maxPerUser = opts.maxPerUser ?? 100;
    this.topN = opts.topN ?? 3;
    // The reference embedder is a deterministic hash, so scores are modest; 0.15 keeps relevant notes in.
    this.threshold = opts.threshold ?? 0.15;
  }

  remember(userId: string, content: unknown, extra: { source?: string; type?: string; tags?: unknown } = {}): { id: string; deduped: boolean } {
    validateUserId(userId);
    const text = checkContent(content);
    const source = (extra.source ?? "care-agent:session-note").trim();
    if (!source || source.length > 80) throw new PolicyError("invalid_source");
    const type = (TYPES as string[]).includes(extra.type ?? "") ? (extra.type as MemoryType) : "personal";
    const tags = Array.isArray(extra.tags)
      ? extra.tags.filter((t): t is string => typeof t === "string" && /^[\w:-]{1,24}$/.test(t)).slice(0, 5)
      : [];
    if (!tags.includes("care")) tags.unshift("care");

    const mine = this.hmem.recordsFor(userId);
    const key = normalise(text);
    const existing = mine.find((m) => normalise(m.content) === key);
    if (existing) {
      this.hmem.store.touch(existing.id);
      return { id: existing.id, deduped: true };
    }
    if (mine.length >= this.maxPerUser) throw new PolicyError("memory_full", `limit of ${this.maxPerUser} notes reached`);

    const now = this.hmem.clock();
    const rec = this.hmem.add({
      content: text, type, tags, source, chatId: userId,
      provenance: { origin: "chat_message", learnedAt: now, label: source },
    });
    return { id: rec.id, deduped: false };
  }

  recall(userId: string, query: unknown, opts: { topN?: number; threshold?: number } = {}): { memories: RecalledNote[]; strategy: string } {
    validateUserId(userId);
    if (typeof query !== "string" || !query.trim()) throw new PolicyError("empty_query");
    const result = this.hmem.query(query, {
      chatId: userId,
      topN: Math.min(Math.max(opts.topN ?? this.topN, 1), 10),
      threshold: opts.threshold ?? this.threshold,
    });
    const memories = result.memories
      .filter((r) => r.memory.chatId === userId) // belt and braces: never return anyone else's note
      .map((r) => ({
        id: r.memory.id, content: r.memory.content, score: Number(r.relevance.toFixed(4)),
        type: r.memory.type, layer: r.memory.layer, confidence: r.memory.confidence, source: r.memory.source,
      }));
    return { memories, strategy: result.trace.strategy };
  }

  feedback(userId: string, memoryId: string, kind: string): { id: string; confidence: number } {
    validateUserId(userId);
    if (!["helpful", "not_helpful", "wrong"].includes(kind)) throw new PolicyError("invalid_feedback");
    const rec = this.hmem.store.get(memoryId);
    if (!rec || rec.chatId !== userId) throw new PolicyError("not_found");
    this.hmem.feedback(memoryId, kind as FeedbackKind);
    return { id: memoryId, confidence: this.hmem.store.get(memoryId)!.confidence };
  }

  exportFor(userId: string): Array<Omit<MemoryRecord, "embedding" | "chatId">> {
    validateUserId(userId);
    return this.hmem.recordsFor(userId).map(({ embedding: _e, chatId: _c, ...rest }) => rest);
  }

  forget(userId: string): { erased: number } {
    validateUserId(userId);
    return { erased: this.hmem.eraseUser(userId) };
  }
}
