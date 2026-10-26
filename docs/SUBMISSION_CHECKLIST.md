# Submission checklist (Open Agent Hackathon 2026)

**Deadline: 27 October 2026, 23:45 UTC. Nothing can be added or fixed after it.** Aim to submit by **mid-day UTC on the 27th**.
The Official Rules on the event page win wherever they disagree with this file.

## Status at a glance

| Requirement | Status | Evidence / what remains |
|---|---|---|
| Zetaris integrated as the data layer | Done | `scripts/setup_zetaris.py`, `/stats`, `docs/SPONSOR_TECHNOLOGY.md` |
| At least one Meterless Engine in a working feature, with a passing test | Done | H-MEM memory; conformance 13/13 twice; `docs/evidence/` |
| Meterless Runtime as the primary AI provider | Done as a provider client; **no live Runtime** (no Ubuntu x86 build) | Staff reply screenshot; see the question below |
| NVIDIA Nemotron through the provider | Done via NVIDIA's hosted API; shows the model per reply | Ask organisers whether this counts for the DGX Spark award |
| Public GitHub repo with README (setup, usage, dependencies) | Done | Re-check from a clean clone (below) |
| Sample inputs and outputs, logs/traces | Done | README tables; `trace` in every `/chat` reply |
| `.env.example`, `SAMPLE_MODE=true` fallback | Done | |
| No keys or credentials committed or on screen | **Check** | commands below |
| Demo video, 1 to 4 minutes | **To do** | `docs/DEMO_SCRIPT.md` |
| Slide deck | **To do** | `docs/DECK_OUTLINE.md` |
| Sponsor technology explanation | Drafted | `docs/SPONSOR_TECHNOLOGY.md`; paste or attach it in the form |
| Pre-existing components declared in the form | **To do** | text to paste below |
| Verified crisis contacts | **To do** | below |
| Fluent-speaker review | **To do** | below |
| Team roster correct before the first submission | **Check** | the team locks on first submission |

## Do these in order

### 1. Verified crisis contacts (safety, 15 minutes)
`/health` shows `verified_crisis_resources: 0` until you add some, so a crisis reply currently has supportive text but **no phone number**.
Look up real emergency and support contacts for Cameroon on **official** sources (government, health ministry, WHO or a recognised hospital or NGO page) and confirm each one.
Put only confirmed entries in `sample_data/crisis_resources.json`:

```json
{"resources": [{"name": "Name of the service", "contact": "the number", "region": "Cameroon", "verified": true}]}
```

Restart the backend, then confirm: `curl -s localhost:8000/health` shows `verified_crisis_resources` greater than 0. Entries with `verified: false` are never shown.

### 2. Fluent-speaker review (30 minutes of their time)
```bash
python scripts/export_translations_for_review.py          # writes docs/evidence/translation_review.csv
```
Give the CSV to a fluent Lamnso speaker (the three columns are explained at the top of the script). **Ask them to check the crisis row most carefully.**
If they correct it, put their wording into `CRISIS_LAMNSO` in `backend/app/safety.py` and remove the `TODO`. Afterwards:
```bash
python scripts/export_translations_for_review.py --summarise docs/evidence/translation_review.csv
```
Use those numbers on the results slide and in the README. If you cannot get a review before the deadline, say so plainly in the deck; do not leave the claim out.

### 3. Clean-clone test (judges can only score what they can run)
```bash
cd /tmp && rm -rf cc && git clone https://github.com/Fai-jr/lamnso-care-agent.git cc && cd cc
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-sample.txt
cp .env.example .env
python -m pytest -q                      # 75 passed, 2 skipped (the 2 need the memory service's Node packages)
WITH_UI=1 bash scripts/run_dev.sh        # open http://localhost:3001, tap a suggestion
```
Then, in the same clone, the full mode: follow README "Full setup" and check `curl localhost:8000/health` shows everything `online`.

### 4. Secrets check
```bash
cd ~/Desktop/lamnso-care-agent
git log -p --all | grep -nE "nvapi-|api[_-]?key *= *[A-Za-z0-9]{20,}|BEGIN .*PRIVATE" | head     # must print nothing
git status --short                       # .env, logs/, data/, node_modules must not be listed
git check-ignore .env logs data          # prints all three
```
If your NVIDIA key was ever pasted anywhere public, revoke it at build.nvidia.com and make a new one. **Revoke the demo key after the judging period.**

### 5. Record and upload the video, build the deck
`docs/DEMO_SCRIPT.md` and `docs/DECK_OUTLINE.md`. Watch the uploaded video once before submitting.

### 6. The submission form (HackOS)
- **Track:** exactly one. Read the challenge statements on HackOS and choose the one that matches mental-health or low-resource-language support. *Wildcard [Tinkerer]* is for existing projects and is **scored only on the new work**; either way, the before/after slide makes the split clear. Track can be changed until the deadline.
- **Project name, description, team members:** confirm the roster before the first submission is created; it locks then.
- **Pre-existing components (paste this):**

> Pre-existing before 22 Oct 2026: (1) the English to Lamnso translation transformer, its SentencePiece tokenizer and the training data it came from (Lamnso dictionary and Bible text, not published); (2) the crisis keyword safety net (`translation/crisis_safety.py`); (3) the Next.js project scaffolding (package.json, config, help page); (4) an earlier Rasa/Django chatbot, kept only in `legacy/` for reference and not used by the submission; (5) the open-source Meterless H-MEM reference implementation and conformance suite (Apache-2.0, `engines/hmem/src` and `engines/hmem/conformance`), with the embedder replaced and a one-line change to the runner's default path. Everything else was built during the build window: the FastAPI backend and pipeline, the Meterless provider client, the Zetaris data layer and setup, the H-MEM privacy layer, service and Python integration, the redesigned UI and splash screen, and the tests and documentation. Full list: `legacy/PRE_EXISTING.md`.

- **Sponsor technology explanation:** paste `docs/SPONSOR_TECHNOLOGY.md`.
- **Links:** public repo, demo video, deck.

## Questions to ask on HackOS (one message each, today)

1. **Meterless channel:** "For the demo requirement of one real request through Nightshift: Nightshift has no Ubuntu x86 build, so we integrated the Meterless Runtime provider contract and tested against NVIDIA's hosted API, as you advised. Is it acceptable to show that in the demo, and does it satisfy the Meterless requirement?" (keep their reply as a screenshot)
2. **NVIDIA channel:** "Does using Nemotron through the provider client against NVIDIA's hosted API qualify for the DGX Spark award, or does it have to run through a Nightshift Runtime?"
3. **If you have a Mac or Windows computer available**, running a Nightshift Runtime there and pointing `METERLESS_BASE_URL` at it (three environment variables) would turn "not exercised against a live Runtime" into a real demo clip. It is optional; do it only if time allows.

## Final hour before submitting

- [ ] Repository is public and the latest commit is pushed (`git status` clean, `git log -1`)
- [ ] README renders; links work; no placeholder text remains
- [ ] Video plays, is under 4:00, shows no keys or personal data
- [ ] Deck exported (PDF and source)
- [ ] Form complete; track selected; roster correct
- [ ] Submitted. Screenshot the confirmation.
