# How Muna uses the sponsor technologies

| Sponsor | What it does in Muna | Where | Proof you can run |
|---|---|---|---|
| **Zetaris** | The data layer: a vetted coping library the agent reads, an interaction log and mood check-ins it writes, live analytics, and real erasure | `backend/app/store.py`, `backend/app/zetaris.py`, `scripts/setup_zetaris.py` | `python scripts/setup_zetaris.py --selftest`, `curl localhost:8000/stats` |
| **Meterless: H-MEM engine** | Opt-in memory across visits: the agent remembers what helps a person, shows what it remembered, and forgets on request | `engines/hmem/`, `backend/app/hmem_client.py`, `backend/app/learning.py` | `npm --prefix engines/hmem run conformance` (13/13) |
| **Meterless: Runtime provider contract** | The model provider client: OpenAI-compatible, bearer token, `meterless-app` header, `/v1/models` health, 429 back-off | `backend/app/nightshift.py` | `python scripts/check_nightshift.py` |
| **NVIDIA Nemotron** | `nvidia/nemotron-3.5-lightning-30b-a3b` writes every reply and the memory notes; the UI and `/stats` show which model answered | provider client, UI | the "Answered by ..." line under each reply |

## Zetaris: the data layer

Zetaris holds everything the agent reads from or writes to a database, in one Iceberg datalake named `lamnso_care`:

| Table | Written by | Read by | Purpose |
|---|---|---|---|
| `resources` | setup script (6 seed rows) | the agent, per message | Vetted coping ideas (slow breathing, grounding, sleep wind-down, a short walk, telling someone you trust, one small step). The model is told it may offer **only** these, so its advice stays inside content a person controls. |
| `interaction_log` | every `/chat` (background) | `GET /stats` | Route, which model answered, latency, translation outcome, whether memory was on. No message text. |
| `checkins` | the 1-to-5 mood buttons | the agent (only if the person turned memory on) | A weekly mood trend the agent may mention gently. Stored under a hashed key; "Forget me" runs a real `DELETE`. |

**How the agent uses it, step by step.** The message is scanned for a topic (sleep, anxiety, stress, low mood, loneliness). Matching topics
become a `SELECT ... FROM lamnso_care.app.resources WHERE ... LIKE '%sleep%'` query. The returned ideas go into the prompt and are shown to the person
as "From the care library: ...". If memory is on, `SELECT COUNT(*), AVG(mood), MIN(mood) FROM lamnso_care.app.checkins WHERE user_key = ...` supplies the trend.

**Engineering that was specific to Zetaris** (found by probing a live instance, then written into `scripts/setup_zetaris.py`):

- Tables must live under a **datalake** (`CREATE DATALAKE ... OPTIONS (storageType 'Local', storagePath ...)`), created with `USING iceberg`.
- The platform only accepts local datalake paths under its local-file-system root (`customer-data/shared`); other paths fail with "Invalid file path to access". The setup script finds that root from the compose file and creates the folder.
- Plain `SHOW NAMESPACES` is disabled and `DROP DATALAKE` is not available, so setup is **idempotent by probing** (`SELECT 1 ... LIMIT 1`) rather than by `IF NOT EXISTS`.
- One JDBC connection is shared by several request threads, so access is serialised with a lock; one statement per call is enforced.
- **No user text ever reaches SQL.** Every value is a number, a hash, or a string from a fixed list or a strict character set. Tests cover injection attempts.
- The self-test proves `INSERT`, `SELECT` and `DELETE ... WHERE` work, which is what makes "Forget me" honest. If deletion ever fails, the app tells the person instead of pretending.

**See it live.** After a few chats, run `curl localhost:8000/stats`, or in the Zetaris UI run:

```sql
SELECT route, model_used, COUNT(*) AS requests, ROUND(AVG(latency_ms)) AS avg_latency_ms
FROM lamnso_care.app.interaction_log GROUP BY route, model_used ORDER BY requests DESC
```

## Meterless: the H-MEM engine

**What it does.** H-MEM stores short memory records with mandatory provenance, ranks them with a hybrid formula, adjusts confidence from feedback,
keeps a trust ledger, and has sleep, dream and conflict services. In Muna it powers one feature: **an opt-in companion memory**.

1. After a normal reply, the model writes up to two short, anonymous, paraphrased notes (never the person's words).
2. The next visit, H-MEM recalls the best matches and the model is told to use them gently.
3. The reply shows "What I remembered" with **Right / Wrong** buttons; those become H-MEM feedback (`helpful` +0.05, `wrong` -0.20 confidence, per the spec).
4. "What do you remember?" lists every note; "Forget me" erases them.

**What is Meterless's and what we wrote.**

| Part | Origin |
|---|---|
| The nine services (`engines/hmem/src/*`) and the conformance suite | Meterless reference implementation, Apache-2.0, vendored unchanged except the item below |
| `embed()` in `src/embeddings.ts` | **Replaced by us** with a deterministic, offline, care-domain embedder (concept axes for anxiety, sleep, low mood, loneliness, ...). The reference's own README says its hash embedder is a mock to be swapped. |
| `index.ts` | **Ours.** Never writes the query text to the audit ledger; `eraseUser()` removes a person's content from state, ledger snapshots and in-memory sleep backups. |
| `care.ts` | **Ours.** Per-user isolation, personal-identifier and prompt-injection rejection, de-duplication, per-user cap, export, erase. |
| `server.ts`, the Python client, the learning step | **Ours.** |

**Why we changed the reference** (measured, not assumed). With the reference's hash embedder, "I feel anxious at night" scored an *exams* note (0.104) the same as the correct
*anxious before bed* note (0.103), and "the weather is nice today" pulled up an unrelated note at 0.157. After the care-domain embedder, relevant notes score 0.23 and above while unrelated queries
stay at or below 0.12, so a threshold of 0.15 separates them. Reading the reference also showed two privacy problems for a mental-health app: it logged every query's text to disk, and deleting a memory left its
content in the ledger. Both are fixed and tested. It also lets records without an owner be visible to everyone; our layer never writes or returns one.

**The test showing it works.**

```bash
npm --prefix engines/hmem run conformance     # 13/13, this repo's engine
# Meterless's own, unmodified runner, pointed at our engine (from a clone of github.com/Meterless/Meterless):
cd Meterless/engines/hmem && HMEM_IMPL=/abs/path/to/lamnso-care-agent/engines/hmem/index.ts npx tsx conformance/runner.ts   # 13/13
npm --prefix engines/hmem test                # 12 tests: isolation, privacy, erase, HTTP, restart persistence
python -m pytest -q                           # includes an end-to-end test against the real service
```

Saved outputs are in `docs/evidence/`. A real restart was also checked by hand: remember, kill the server, start a new one, recall still works, then "forget" left zero copies of the note on disk.

## Meterless: Runtime (Nightshift) as the AI provider

`backend/app/nightshift.py` implements the Meterless Runtime provider contract used by every model call (replies and memory notes):

- OpenAI-compatible `POST /v1/chat/completions`, base URL normalised so it never becomes `/v1/v1`; `Authorization: Bearer <token>`; `meterless-app` and `meterless-scope` headers.
- Health from `GET /v1/models` (`401/403` means a wrong token); retries on `429` after 2, 4 and 8 seconds; a 180-second timeout for model loads.
- The model that actually answered is read from the response and shown in the UI, the trace and `/stats`.
- Pointing it at a Meterless Runtime is three environment variables (`METERLESS_BASE_URL`, `METERLESS_RUNTIME_TOKEN`, `METERLESS_MODEL=meterless/auto`) and no code change.

**Honest status.** Nightshift's current Linux build is for NVIDIA DGX Spark (ARM64); there is no Ubuntu x86_64 installer, and the Mac and Windows editions could not be used on the development machine.
Meterless staff confirmed on the hackathon channel that the requirement can be met by integrating the Meterless Runtime as a provider alongside an engine, and by testing against NVIDIA's hosted API.
That is what was done: the client is tested against a mock Runtime in the test-suite (headers, retry, unauthorised, health) and against NVIDIA's hosted endpoint live.
It has **not** been exercised against a running Meterless Runtime.

## NVIDIA Nemotron

`nvidia/nemotron-3.5-lightning-30b-a3b` writes every reply and the memory notes, through the provider client. It fits the job: a small active-parameter model that answers in about 0.6 to 1.8 seconds
and follows the "two or three very short sentences, plain words, no contractions" instruction that makes the reply easier for the Lamnso translator. Thinking mode is switched off per request
(`chat_template_kwargs.enable_thinking=false`) so the token budget goes to the answer. The UI shows the model name under every reply and `/stats` counts requests per model, so "which model handled this request" is always answerable.

## What is unique about how Muna uses them

- **The language bridge.** A general model reasons; the team's own transformer, trained on a language no commercial model serves well, delivers the answer in Lamnso. The pipeline translates sentence by sentence, catches looping output, retries once with a simpler reply, and shows no Lamnso at all rather than wrong Lamnso.
- **The data layer is part of the agent's judgement.** The model may only offer coping ideas that exist in a Zetaris table, so advice is bounded by content a human curates, and the log makes every request auditable.
- **Memory with consent and real erasure.** H-MEM was hardened for a sensitive setting: opt-in, paraphrased notes, per-person isolation, no query text on disk, and a delete that actually deletes (checked by reading the files).
- **Measured, not assumed.** The embedder swap, the privacy fixes and the translation guard each came from a measurement shown above.
