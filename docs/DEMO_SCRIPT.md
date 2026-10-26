# Demo video script (target 3 min 30 s, hard limit 4 min)

The video is worth 15 points: **show the agent working, not slides about it.** Record real runs, no hard-coded paths.

## Before you press record (15 minutes)

- [ ] `bash scripts/run_dev.sh` with `WITH_UI=1` and `SAMPLE_MODE=false`; `curl localhost:8000/health` shows `nightshift`, `zetaris`, `hmem` all `online`, translator `lamnso-transformer`
- [ ] Open **http://localhost:3001 in a private/incognito window** so the splash screen shows (it appears once per browser session)
- [ ] Fill verified crisis contacts in `sample_data/crisis_resources.json` (see the checklist); restart the backend
- [ ] Clear old demo data: Settings, then **Forget me**. Fresh start means the memory demo is honest
- [ ] Send one throwaway message first (the first model call is slower)
- [ ] Use only invented messages. Never real personal stories
- [ ] **Never show** `.env`, your NVIDIA key, or terminal history containing keys. Do not run `cat .env`; use `grep -E '^METERLESS_(BASE_URL|MODEL)=' .env` if you need to show settings
- [ ] Two windows ready: the browser (UI) and one terminal with a large font. Screen 1080p, notifications off
- [ ] Rehearse once with a timer

## Shot list and narration

| Time | On screen | Say (adapt to your voice) |
|---|---|---|
| 0:00 to 0:15 | The **splash**: the "m" badge, heart, "Your calm companion" (about 4 s), then the chat screen | "Lamnso is spoken by hundreds of thousands of people in Cameroon, and almost no mental-health tool speaks it. This is Muna." |
| 0:15 to 0:40 | The hero card; settings gear | "Muna is a calm companion for people who are stressed, can't sleep or feel alone. A modern model thinks. Our own transformer, trained on Lamnso, speaks. And everything personal stays under the person's control." |
| 0:40 to 1:20 | Tap **Help me sleep better**. Point at: Lamnso sentences with English underneath; "Answered by nvidia/nemotron-3.5-lightning-30b-a3b"; "From the care library: Wind down for sleep" | "Nemotron writes two or three very short sentences. Our model translates one sentence at a time, and if it can't do it reliably it shows English only, never wrong Lamnso. The suggestion comes from a coping library stored in **Zetaris**; the model may offer nothing outside it." |
| 1:20 to 2:00 | Settings, switch on **Remember what helps me**. Send "I feel anxious at night and I cannot sleep". Wait 6 s. Tap **New chat**. Send "It is night again and I am anxious". Open **What I remembered**; press **Right**. Then Settings, **What do you remember?** | "Memory is off by default. With it on, after a reply the model saves one or two short anonymous notes, never my words. Next visit, **Meterless H-MEM** recalls them, and I can see exactly what it used and say right or wrong, which adjusts its confidence." |
| 2:00 to 2:25 | Type a crisis test phrase. The amber alert appears with no model label | "Safety comes first. A keyword check runs before any model, translation or memory, and answers with fixed text and verified contacts. Nothing here depends on a network." |
| 2:25 to 3:00 | Terminal: `curl -s localhost:8000/stats \| python3 -m json.tool`. Then the Zetaris UI running the `interaction_log` SELECT from `docs/SPONSOR_TECHNOLOGY.md`. | "Every request is logged in Zetaris with the route, the model and the latency, no message text. This is a live query: which model answered how many requests." |
| 3:00 to 3:25 | Terminal: `npm --prefix engines/hmem run conformance` (13/13), then the upstream runner line from `docs/evidence/` | "The memory engine passes Meterless's conformance suite 13 out of 13, including their own unmodified runner. We replaced the embedder, and fixed two privacy problems we found: query text in the audit log, and deletion that left content behind." |
| 3:25 to 3:40 | Settings, **Forget me**, confirm. Then **What do you remember?** shows "Nothing yet." | "And Forget me really forgets: notes and mood check-ins." |
| 3:40 to 4:00 | Back to the hero card or the logo | "Honest limits: English input only, translation is modest and needs a fluent speaker's review, and Meterless's runtime has no Ubuntu build, so we tested the provider against NVIDIA's API. Next: Lamnso to English and a clinical review. Thank you." |

If you run long, cut the mood check-in and shorten the terminal section. **Do not go over 4:00.**

## Make it count

- Say the sponsor names aloud as each one appears (Zetaris, Meterless, NVIDIA Nemotron)
- Keep the cursor still while you talk, and pause one second on each proof (model label, 13/13, `/stats`)
- Upload the finished video and **watch it once end to end** before submitting
