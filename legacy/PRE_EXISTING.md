# Pre-existing components

These existed before the hackathon build window (22 Oct 2026, 00:00 UTC) and are declared as such.

| Component | Location here | Origin / notes |
|---|---|---|
| Lamnso–English translation model (PyTorch transformer) | translation/integrate.py, weights via GitHub Release | Trained before the hackathon |
| SentencePiece tokenizer | translation/lamnso_tokenizer.model | Trained before the hackathon |
| Next.js chat UI (adapted) | frontend/ | Existing project, modified for this build |
| Training data (not published) | not in repo | English–Lamnso pairs derived from the Lamnso dictionary and Bible translation; redistribution terms being verified |

## New in this hackathon
Everything else: the FastAPI backend, Zetaris integration, Nightshift client, Meterless H-MEM engine,
crisis-routing logic, tests, and evaluation.

## Privacy
No real user conversations or personal data are included. All sample data is synthetic.
