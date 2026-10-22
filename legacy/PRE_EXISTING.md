# Pre-existing components

These existed before the hackathon build window (22 Oct 2026, 00:00 UTC) and are declared as such.

| Component | Location here | Notes |
|---|---|---|
| Lamnso <-> English translation model (PyTorch transformer) | translation/model.py (architecture, extracted unchanged), weights via GitHub Release | Trained before the hackathon. Used English -> Lamnso only. |
| SentencePiece tokenizer | translation/lamnso_tokenizer.model | Trained before the hackathon |
| Crisis keyword safety net | translation/crisis_safety.py | Reused unchanged |
| Original Rasa-based pipeline | legacy/integrate_rasa.py, legacy/crisis_responder.py, legacy/greeting_shortcuts.py, legacy/mental_health_keywords.py | Kept for reference only; NOT used by the new app |
| Next.js chat UI | frontend/ | Existing project, adapted for this build |
| Training data (not published) | not in repo | English-Lamnso pairs from the Lamnso dictionary and Bible translation; redistribution terms being verified |

## New in this hackathon

- FastAPI backend (backend/app): pipeline, Nightshift client, safety wrapper, memory seam, tracing
- translation/translator.py (wrapper with sample mode), translation/download_weights.py
- Tests (tests/), Zetaris integration, Meterless engine work (in progress)

## Privacy

No real user conversations or personal data are included. All sample data is synthetic. Message text is not
logged by default.
