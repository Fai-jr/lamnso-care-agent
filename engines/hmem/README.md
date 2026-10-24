# H-MEM engine (Meterless) for the Lamnso Care Agent

Long-term memory so the agent can remember what helps a person across sessions. It implements the Meterless
**H-MEM** spec (`AGENTS.md` in https://github.com/Meterless/Meterless/tree/main/engines/hmem): tiered records
with mandatory provenance, the hybrid ranking formula, feedback deltas, trust ledger, sleep/dream/conflict services.

## What is ours and what is Meterless's

| Part | Origin |
|---|---|
| `src/*.ts` (the 9 services), `conformance/` | Meterless reference implementation, Apache-2.0 (see `NOTICE`) |
| `src/embeddings.ts` `embed()` | **Replaced**: deterministic care-domain embedder (the reference hash mock is meant to be swapped) |
| `index.ts` | **New**: audit ledger never stores query text; `eraseUser()` removes content from state, ledger and backups |
| `care.ts` | **New**: per-user isolation, personal-identifier and prompt-injection rejection, dedupe, per-user cap, export, erase |
| `server.ts` | **New**: localhost-only HTTP service used by the Python backend |
| `test/` | **New**: 12 tests |

## Run

```bash
npm --prefix engines/hmem install      # once
npm --prefix engines/hmem run serve    # http://127.0.0.1:8765, data in ./data/hmem (git-ignored)
```

## Prove it works

```bash
npm --prefix engines/hmem run conformance     # 13/13, using this repo's engine
npm --prefix engines/hmem test                # 12 tests: isolation, privacy, erase, HTTP, restart persistence

# Meterless's own, unmodified runner against this engine (needs a clone of the Meterless repo):
cd ~/Meterless/engines/hmem && HMEM_IMPL=/ABS/PATH/TO/engines/hmem/index.ts npx tsx conformance/runner.ts
```

## Privacy rules enforced by the service (not just by the client)

- Every read and write is bound to a pseudonymous user key (a hash; the raw browser id never reaches the service).
- Notes are 8-200 characters; e-mail addresses, links, phone numbers/long digit runs and @handles are rejected.
- Instruction-like text ("ignore previous instructions...") is rejected, so memory cannot be used to inject prompts.
- Raw messages are never stored. The Python side stores model-written, paraphrased notes only, and only when the
  person has switched memory on, after a normal reply, never for crisis messages.
- Export (`POST /memory/export`) and real erasure (`POST /memory/forget`) are first-class.
