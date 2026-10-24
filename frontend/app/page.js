"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

const newId = () =>
  globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;

function readStored(key, fallback) {
  try {
    const v = window.localStorage.getItem(key);
    return v === null ? fallback : v;
  } catch {
    return fallback;
  }
}
function writeStored(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* private mode: the page still works, settings just are not remembered */
  }
}

async function api(path, body) {
  let res;
  try {
    res = await fetch(`${API}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error("I cannot reach the care service right now. Please check that it is running and try again.");
  }
  if (!res.ok) {
    let detail = "";
    try {
      detail = (await res.json()).detail || "";
    } catch {
      /* no JSON body */
    }
    throw new Error(detail || `The service answered with an error (${res.status}).`);
  }
  return res.json();
}

function Reply({ data, showEnglish }) {
  if (data.route === "crisis") {
    return (
      <div role="alert" className="rounded-2xl border border-amber-300 bg-amber-50 p-4 text-amber-950">
        <p className="mb-1 text-xs font-semibold uppercase tracking-wide">You are not alone</p>
        {data.reply_lamnso && <p lang="lns" className="text-base font-medium">{data.reply_lamnso}</p>}
        {data.reply_english && <p className="mt-2 text-sm">{data.reply_english}</p>}
      </div>
    );
  }
  const pairs = data.sentences?.length ? data.sentences : [{ english: data.reply_english, lamnso: null }];
  const anyLamnso = pairs.some((p) => p.lamnso);
  return (
    <div className="rounded-2xl rounded-tl-sm bg-white p-4 shadow-sm ring-1 ring-slate-200">
      <div className="space-y-2">
        {pairs.map((p, i) => (
          <div key={i}>
            {p.lamnso && <p lang="lns" className="text-base font-medium text-slate-900">{p.lamnso}</p>}
            {(showEnglish || !p.lamnso) && <p className="text-sm text-slate-600">{p.english}</p>}
          </div>
        ))}
      </div>
      {!anyLamnso && data.route === "agent" && (
        <p className="mt-3 text-xs text-slate-500">
          I could not translate this reply into Lamnso reliably, so I am showing it in English only.
        </p>
      )}
    </div>
  );
}

function Meta({ data, onFeedback }) {
  if (data.route === "crisis") return null;
  const used = data.memories_used || [];
  return (
    <div className="mt-1 space-y-1 pl-1 text-xs text-slate-500">
      <p>
        {data.model_used ? <>Answered by <span className="font-mono">{data.model_used}</span></> : data.route.replaceAll("_", " ")}
        {data.memory_enabled && <> · memory on, used {used.length} note{used.length === 1 ? "" : "s"}</>}
      </p>
      {data.ideas_used?.length > 0 && (
        <p>From the care library: {data.ideas_used.map((i) => i.title).join(", ")}</p>
      )}
      {used.length > 0 && (
        <details>
          <summary className="cursor-pointer select-none">What I remembered</summary>
          <ul className="mt-1 space-y-1">
            {used.map((m) => (
              <li key={m.id} className="flex items-center gap-2">
                <span className="flex-1">{m.content}</span>
                <button type="button" onClick={() => onFeedback(m.id, "helpful")} aria-label={`This note is right: ${m.content}`}
                  className="rounded px-1.5 ring-1 ring-slate-300 hover:bg-slate-100">Right</button>
                <button type="button" onClick={() => onFeedback(m.id, "wrong")} aria-label={`This note is wrong: ${m.content}`}
                  className="rounded px-1.5 ring-1 ring-slate-300 hover:bg-slate-100">Wrong</button>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

export default function Home() {
  const [ready, setReady] = useState(false);
  const [userId, setUserId] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [memoryOn, setMemoryOn] = useState(false);
  const [showEnglish, setShowEnglish] = useState(true);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notes, setNotes] = useState(null);
  const endRef = useRef(null);

  useEffect(() => {
    let id = readStored("care_user_id", "");
    if (!id) {
      id = newId();
      writeStored("care_user_id", id);
    }
    setUserId(id);
    setSessionId(`s-${newId()}`);
    setMemoryOn(readStored("care_memory", "0") === "1");
    setShowEnglish(readStored("care_show_english", "1") === "1");
    setReady(true);
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);

  const addMessage = useCallback((m) => setMessages((prev) => [...prev, { id: newId(), ...m }]), []);

  async function send(e) {
    e?.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setError("");
    addMessage({ role: "user", text });
    setBusy(true);
    try {
      const data = await api("/chat", { message: text, session_id: sessionId, user_id: userId, remember: memoryOn });
      addMessage({ role: "assistant", data });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function showNotes() {
    setError("");
    try {
      setNotes((await api("/memory/export", { user_id: userId })).memories);
    } catch (err) {
      setError(err.message);
    }
  }

  async function forgetAll() {
    if (!window.confirm("Erase everything I remember about you? This cannot be undone.")) return;
    setError("");
    try {
      const { erased } = await api("/memory/forget", { user_id: userId });
      setNotes(null);
      addMessage({ role: "system", text: `Done. I erased ${erased} note${erased === 1 ? "" : "s"} about you.` });
    } catch (err) {
      setError(err.message);
    }
  }

  async function feedback(memoryId, kind) {
    try {
      await api("/memory/feedback", { user_id: userId, memory_id: memoryId, kind });
      addMessage({ role: "system", text: kind === "wrong" ? "Thanks, I will trust that note less." : "Thanks, I will trust that note more." });
    } catch (err) {
      setError(err.message);
    }
  }

  async function checkin(mood) {
    setError("");
    try {
      await api("/checkin", { user_id: userId, mood });
      addMessage({ role: "system", text: "Check-in saved. Thank you for telling me." });
    } catch (err) {
      setError(err.message);
    }
  }

  const toggleMemory = (v) => { setMemoryOn(v); writeStored("care_memory", v ? "1" : "0"); };
  const toggleEnglish = (v) => { setShowEnglish(v); writeStored("care_show_english", v ? "1" : "0"); };

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col gap-3 bg-slate-50 p-4 text-slate-900">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Lamnso Care Companion</h1>
          <p className="text-sm text-slate-600">A gentle space to talk. Replies are written in English by an AI and translated into Lamnso.</p>
        </div>
        <Link href="/help" className="shrink-0 rounded-lg px-3 py-1.5 text-sm ring-1 ring-slate-300 hover:bg-white">Help</Link>
      </header>

      <p className="rounded-xl bg-slate-100 p-3 text-xs text-slate-600">
        This is not a substitute for professional care. If you are in danger, contact your local emergency services.
        For now please write in English. Machine translation can be imperfect, so the English is always available.
      </p>

      <section aria-label="Settings" className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-xl bg-white p-3 text-sm ring-1 ring-slate-200">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={memoryOn} onChange={(e) => toggleMemory(e.target.checked)} className="h-4 w-4" />
          Remember what helps me between visits
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={showEnglish} onChange={(e) => toggleEnglish(e.target.checked)} className="h-4 w-4" />
          Show English under Lamnso
        </label>
        <span className="ml-auto flex gap-2">
          <button type="button" onClick={showNotes} className="rounded-lg px-3 py-1 ring-1 ring-slate-300 hover:bg-slate-50">What do you remember?</button>
          <button type="button" onClick={forgetAll} className="rounded-lg px-3 py-1 text-red-700 ring-1 ring-red-200 hover:bg-red-50">Forget me</button>
        </span>
        {memoryOn && (
          <p className="basis-full text-xs text-slate-500">
            Memory is on: after a normal reply I save one or two short, anonymous notes (never your exact words, never anything from a crisis message).
          </p>
        )}
      </section>

      <section aria-label="Mood check-in" className="flex flex-wrap items-center gap-2 rounded-xl bg-white p-3 text-sm ring-1 ring-slate-200">
        <span>How are you feeling right now?</span>
        {[1, 2, 3, 4, 5].map((n) => (
          <button key={n} type="button" onClick={() => checkin(n)}
            aria-label={`Mood ${n} of 5${n === 1 ? ", very low" : n === 5 ? ", good" : ""}`}
            className="h-8 w-8 rounded-full ring-1 ring-slate-300 hover:bg-slate-100">{n}</button>
        ))}
        <span className="text-xs text-slate-500">1 = very low, 5 = good. Saved under an anonymous key; &ldquo;Forget me&rdquo; erases it.</span>
      </section>

      {notes && (
        <section aria-label="Remembered notes" className="rounded-xl bg-white p-3 text-sm ring-1 ring-slate-200">
          <div className="mb-1 flex items-center justify-between">
            <h2 className="font-medium">What I remember about you</h2>
            <button type="button" onClick={() => setNotes(null)} className="text-xs text-slate-500 underline">Close</button>
          </div>
          {notes.length === 0 ? <p className="text-slate-500">Nothing yet.</p> : (
            <ul className="list-disc space-y-1 pl-5">{notes.map((n) => <li key={n.id}>{n.content}</li>)}</ul>
          )}
        </section>
      )}

      <section aria-label="Conversation" aria-live="polite" className="flex flex-1 flex-col gap-3 overflow-y-auto py-2">
        {ready && messages.length === 0 && (
          <p className="m-auto max-w-sm text-center text-sm text-slate-500">
            Tell me how you are feeling today. There is no rush.
          </p>
        )}
        {messages.map((m) =>
          m.role === "user" ? (
            <div key={m.id} className="ml-auto max-w-[85%] rounded-2xl rounded-tr-sm bg-slate-800 px-4 py-2 text-sm text-white">{m.text}</div>
          ) : m.role === "system" ? (
            <p key={m.id} className="text-center text-xs text-slate-500">{m.text}</p>
          ) : (
            <div key={m.id} className="max-w-[92%]">
              <Reply data={m.data} showEnglish={showEnglish} />
              <Meta data={m.data} onFeedback={feedback} />
            </div>
          )
        )}
        {busy && <p className="text-sm text-slate-500">Thinking…</p>}
        <div ref={endRef} />
      </section>

      {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-800 ring-1 ring-red-200">{error}</p>}

      <form onSubmit={send} className="sticky bottom-0 flex items-end gap-2 bg-slate-50 pb-2">
        <label htmlFor="msg" className="sr-only">Your message</label>
        <textarea id="msg" value={input} onChange={(e) => setInput(e.target.value)} rows={2} maxLength={2000}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) send(e); }}
          placeholder="Write how you feel… (Enter to send)"
          className="flex-1 resize-none rounded-xl border-0 bg-white p-3 text-sm ring-1 ring-slate-300 focus:ring-2 focus:ring-slate-500" />
        <button type="submit" disabled={busy || !input.trim()}
          className="rounded-xl bg-slate-800 px-4 py-3 text-sm font-medium text-white disabled:opacity-40">Send</button>
      </form>
    </main>
  );
}
