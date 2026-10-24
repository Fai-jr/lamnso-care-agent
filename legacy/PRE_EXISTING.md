# Pre-existing components

These existed before the hackathon build window (22 Oct 2026, 00:00 UTC) and are declared as such.

| Component | Location here | Notes |
|---|---|---|
| Lamnso <-> English translation model (PyTorch transformer) | translation/model.py (architecture, extracted unchanged), weights via GitHub Release | Trained before the hackathon. Used English -> Lamnso only. |
| SentencePiece tokenizer | translation/lamnso_tokenizer.model | Trained before the hackathon |
| Crisis keyword safety net | translation/crisis_safety.py | Reused unchanged |
| Original Rasa-based pipeline | legacy/integrate_rasa.py, legacy/crisis_responder.py, legacy/greeting_shortcuts.py, legacy/mental_health_keywords.py | Kept for reference only; NOT used by the new app |
| H-MEM engine core (9 services + conformance suite) | engines/hmem/src, engines/hmem/conformance | Open source (Apache-2.0) from github.com/Meterless/Meterless; see engines/hmem/NOTICE. `embed()` was replaced, `conformance/runner.ts` has a one-line default-path change |
| Next.js project scaffolding | frontend/ (layout, styles, help page, config) | Existing project files, kept as they were |
| Training data (not published) | not in repo | English-Lamnso pairs from the Lamnso dictionary and Bible translation; redistribution terms being verified |

## New in this hackathon

- frontend/app/page.js: the chat page was rewritten from scratch for this build (bilingual replies, memory switch,
  "what do you remember" / "forget me", model label, crisis display)
- FastAPI backend (backend/app): pipeline, Nightshift client, safety wrapper, memory seam, tracing
- translation/translator.py (wrapper with sample mode), translation/download_weights.py
- H-MEM integration: engines/hmem/index.ts, care.ts, server.ts, care-domain embedder, privacy policy, tests;
  backend/app/hmem_client.py, learning.py, memory endpoints (export / forget / feedback)
- Tests (tests/), Zetaris integration (in progress)

## Privacy

No real user conversations or personal data are included. All sample data is synthetic. Message text is not
logged by default.
