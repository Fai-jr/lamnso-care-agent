# Slide deck outline

The submission asks for eight things in the deck: **problem and users, solution, workflow/architecture, technical stack, how Zetaris and Meterless were used,
what was unique about the sponsor technology, product visuals, future enhancements.** Slides 2 to 13 cover them. Aim for 12 to 14 slides, big visuals, few words.

| # | Slide | Content | Visual to capture |
|---|---|---|---|
| 1 | **Muna: your calm companion** | One line: "mental-wellbeing support in Lamnso". Team, track, repo link | The logo and splash |
| 2 | **The problem and who it is for** | Lamnso: a language of Cameroon with almost no digital mental-health tools. People who are stressed, cannot sleep or feel alone, and who can't use English-only apps comfortably. Why existing tools fail: language, privacy, trust | A photo-free graphic; the problem in one sentence |
| 3 | **The solution** | A calm companion: the model thinks in English, our own transformer speaks Lamnso, English always shown underneath. Short, plain replies; vetted coping ideas; memory only with consent | The chat screen with a bilingual reply |
| 4 | **How the agent works** | The pipeline: crisis check first, memory (opt-in), Zetaris library, Nemotron reply, sentence-by-sentence Lamnso, retry, log | The mermaid diagram from the README exported as an image |
| 5 | **Technical stack** | Next.js 16 / React 19 / Tailwind 4, FastAPI, PyTorch transformer + SentencePiece, Node/TypeScript H-MEM service, Zetaris (JDBC, Iceberg), Nemotron 3.5 Lightning | A simple icon row |
| 6 | **Zetaris: the data layer** | Three tables (`resources`, `interaction_log`, `checkins`); the agent reads the coping library by SQL and may offer nothing else; live `/stats`; real `DELETE`; engineering lessons (datalake path rules, idempotent setup) | The `/stats` output and the Zetaris SQL result |
| 7 | **Meterless: H-MEM and the provider contract** | Opt-in memory; conformance 13/13 on our runner and on Meterless's unmodified runner; what is theirs vs ours; honest note on the runtime (no Ubuntu x86 build) | The two "13/13 checks passed" screens |
| 8 | **We measured, then changed the engine** | Reference hash embedder: exams note 0.104 vs the right note 0.103; "weather is nice" retrieved an unrelated note at 0.157. After the care-domain embedder: relevant at or above 0.23, unrelated at or below 0.12. Plus two privacy fixes | A before/after table |
| 9 | **NVIDIA Nemotron** | `nvidia/nemotron-3.5-lightning-30b-a3b` writes every reply and note; the model label under each reply; about 0.6 to 1.8 s per request | The "Answered by ..." label |
| 10 | **What is unique** | The language bridge; data layer bounds the advice; memory with consent and verified erasure; measured design decisions | Three icons |
| 11 | **Safety and responsible AI** | Crisis path first and offline; no message text in logs; opt-in memory; erasure; honest translation guard; not a substitute for professional care | The amber crisis screen (with verified contacts) |
| 12 | **Results and evidence** | 79 backend tests, 12 engine tests, 24 UI tests, conformance 13/13 twice. Translation: checkpoint BLEU 7.45 and val_loss 2.90; **fluent-speaker review: fill in from `scripts/export_translations_for_review.py --summarise`**; Lamnso shown for N of M test messages | The summary table |
| 13 | **Product visuals** | Splash, hero card, a bilingual reply, memory notes, crisis alert, Sage and Sky themes, settings | 4 to 6 screenshots |
| 14 | **Before and after the hackathon** | Before: translation model and tokenizer, crisis keyword net, an older Rasa/Django chatbot (not used). During: FastAPI pipeline, Zetaris layer, provider client, H-MEM integration and hardening, the redesigned UI and splash, tests, docs | A two-column table |
| 15 | **Future enhancements** | Lamnso to English translation (reverse model); a clinical and community review of the coping library and wording; more verified local contacts; a live Meterless Runtime on a Mac/Windows/DGX host; offline PWA | A roadmap line |

## Tips

- Every claim on a slide should point at something the judges can run (a command, a file, a number in `docs/evidence/`)
- Use the real numbers from your own runs; leave the speaker-review line empty rather than guess
- Export the deck as PDF as well as the original file
