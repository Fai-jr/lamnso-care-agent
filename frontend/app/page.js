"use client";

import Link from "next/link";
import { useCallback, useEffect, useId, useRef, useState } from "react";

const APP_NAME = "Muna"; // change this one constant to rename the companion
const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const SPLASH_MS = 3600; // shown for 3.6 s, then a 0.4 s exit: about 4 s in total
const SUGGESTIONS = ["I feel stressed about school", "Help me sleep better", "Guide me through breathing"];

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
    /* private mode: settings are simply not remembered */
  }
}

function readSession(key) {
  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return null;
  }
}
function writeSession(key, value) {
  try {
    window.sessionStorage.setItem(key, value);
  } catch {
    /* private mode: the splash simply shows again next time */
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
    throw new Error(typeof detail === "string" && detail ? detail : `The service answered with an error (${res.status}).`);
  }
  return res.json();
}

/* ---------- small original icons and mascot ---------- */
function Avatar({ size = 64 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label={`${APP_NAME}, a friendly round companion`} className="muna-bob shrink-0">
      <defs>
        <radialGradient id="av" cx="35%" cy="30%" r="75%">
          <stop offset="0%" stopColor="var(--avatar-1)" />
          <stop offset="100%" stopColor="var(--avatar-2)" />
        </radialGradient>
      </defs>
      <circle cx="32" cy="34" r="26" fill="url(#av)" />
      <path d="M21 31 q3.5 -5 7 0" stroke="#17332d" strokeWidth="2.4" fill="none" strokeLinecap="round" />
      <path d="M36 31 q3.5 -5 7 0" stroke="#17332d" strokeWidth="2.4" fill="none" strokeLinecap="round" />
      <ellipse cx="19" cy="40" rx="4" ry="2.6" fill="#F7A8A8" opacity="0.7" />
      <ellipse cx="45" cy="40" rx="4" ry="2.6" fill="#F7A8A8" opacity="0.7" />
      <path d="M26 42 q6 6 12 0" stroke="#17332d" strokeWidth="2.4" fill="none" strokeLinecap="round" />
      <path d="M52 8 c-2.6 -4 -8 -1.6 -5.6 3 L52 17 l5.6 -6 c2.4 -4.6 -3 -7 -5.6 -3z" fill="#E5484D" />
    </svg>
  );
}
const MicIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <rect x="9" y="3" width="6" height="12" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
  </svg>
);
const SendIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M5 12h14M13 6l6 6-6 6" />
  </svg>
);
const GearIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
  </svg>
);

/* ---------- brand logo: periwinkle badge with a white lowercase "m" ---------- */
const M_PATH = "M27 71 V41 M27 53 C27 44 32 39 39 39 C46 39 50 44 50 52 V71 M50 52 C50 44 55 39 62 39 C69 39 73 44 73 52 V71";

function Logo({ size = 36, shimmer = false }) {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");
  return (
    <svg viewBox="0 0 100 100" aria-hidden="true" focusable="false" className="block shrink-0" style={{ width: size, height: size }}>
      <defs>
        <linearGradient id={`lg${uid}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#5786E4" />
          <stop offset="1" stopColor="#4373CE" />
        </linearGradient>
        {shimmer && (
          <>
            <mask id={`lm${uid}`} maskUnits="userSpaceOnUse" x="0" y="0" width="100" height="100">
              <path d={M_PATH} fill="none" stroke="#fff" strokeWidth="8.5" strokeLinecap="round" strokeLinejoin="round" />
            </mask>
            <linearGradient id={`ls${uid}`} x1="0" y1="0" x2="1" y2="0">
              <stop offset="0" stopColor="#fff" stopOpacity="0" />
              <stop offset="0.5" stopColor="#CFE0FF" stopOpacity="0.95" />
              <stop offset="1" stopColor="#fff" stopOpacity="0" />
            </linearGradient>
          </>
        )}
      </defs>
      <rect width="100" height="100" rx="28" fill={`url(#lg${uid})`} />
      <path d={M_PATH} fill="none" stroke="#fff" strokeWidth="8.5" strokeLinecap="round" strokeLinejoin="round" />
      {shimmer && (
        <g mask={`url(#lm${uid})`}>
          <g transform="skewX(-18)">
            <rect className="muna-shine" x="-40" y="20" width="36" height="60" fill={`url(#ls${uid})`} />
          </g>
        </g>
      )}
    </svg>
  );
}

function Heart({ size = 30 }) {
  return (
    <svg viewBox="0 0 32 28" aria-hidden="true" focusable="false" className="block" style={{ width: size, height: (size * 28) / 32 }}>
      <path d="M16 26 C6 18 2 13 2 8.5 C2 4.6 5 2 8.4 2 C11.6 2 14.4 3.8 16 6.6 C17.6 3.8 20.4 2 23.6 2 C27 2 30 4.6 30 8.5 C30 13 26 18 16 26 Z" fill="#F88D7A" />
    </svg>
  );
}

/* ---------- splash: brand intro, then the chat. Tap, Enter, Space or Escape skips it. ---------- */
function Splash({ onDone }) {
  const [leaving, setLeaving] = useState(false);
  const ref = useRef(null);
  const leave = useCallback(() => setLeaving(true), []);
  useEffect(() => {
    ref.current?.focus();
    const t = setTimeout(leave, SPLASH_MS);
    return () => clearTimeout(t);
  }, [leave]);
  useEffect(() => {
    if (!leaving) return undefined;
    const t = setTimeout(onDone, 400);
    return () => clearTimeout(t);
  }, [leaving, onDone]);
  return (
    <div ref={ref} role="button" tabIndex={0} aria-label={`${APP_NAME}, your calm companion. Press to continue.`}
      className={`muna-splash${leaving ? " leaving" : ""}`} onClick={leave}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " " || e.key === "Escape") {
          e.preventDefault();
          leave();
        }
      }}>
      <div className="sp-stack">
        <div className="sp-heart-wrap"><div className="sp-heart"><Heart /></div></div>
        <div className="sp-badge-wrap"><div className="sp-badge"><Logo size="var(--sp-badge)" shimmer /></div></div>
        <p className="sp-word">{APP_NAME}</p>
        <p className="sp-tag">Your calm companion</p>
        <div className="sp-divider" />
      </div>
      <div className="sp-lockup"><Logo size={48} /><span>{APP_NAME}</span></div>
    </div>
  );
}

/* ---------- reply rendering ---------- */
function Reply({ data, showEnglish }) {
  if (data.route === "crisis") {
    return (
      <div role="alert" className="rounded-[20px] border border-amber-300 bg-amber-50 p-4 text-amber-950">
        <p className="mb-1 text-xs font-bold uppercase tracking-wide">You are not alone</p>
        {data.reply_lamnso && <p lang="lns" className="text-base font-semibold">{data.reply_lamnso}</p>}
        {data.reply_english && <p className="mt-2 text-sm">{data.reply_english}</p>}
      </div>
    );
  }
  const pairs = data.sentences?.length ? data.sentences : [{ english: data.reply_english, lamnso: null }];
  const anyLamnso = pairs.some((p) => p.lamnso);
  return (
    <div className="muna-reply">
      <div className="space-y-2.5">
        {pairs.map((p, i) => (
          <div key={i}>
            {p.lamnso && <p lang="lns" className="text-[17px] font-semibold leading-snug" style={{ color: "var(--heading)" }}>{p.lamnso}</p>}
            {(showEnglish || !p.lamnso) && <p className="text-[15px]">{p.english}</p>}
          </div>
        ))}
      </div>
      {!anyLamnso && data.route === "agent" && (
        <p className="mt-3 text-xs opacity-80">I could not translate this reply into Lamnso reliably, so I am showing it in English only.</p>
      )}
    </div>
  );
}

function Meta({ data, onFeedback }) {
  if (data.route === "crisis") return null;
  const used = data.memories_used || [];
  return (
    <div className="mt-1.5 space-y-1 pl-1 text-xs opacity-90">
      <p>
        {data.model_used ? <>Answered by <span className="font-mono">{data.model_used}</span></> : data.route.replaceAll("_", " ")}
        {data.memory_enabled && <> · memory on, used {used.length} note{used.length === 1 ? "" : "s"}</>}
      </p>
      {data.ideas_used?.length > 0 && <p>From the care library: {data.ideas_used.map((i) => i.title).join(", ")}</p>}
      {used.length > 0 && (
        <details>
          <summary className="cursor-pointer select-none">What I remembered</summary>
          <ul className="mt-1 space-y-1.5">
            {used.map((m) => (
              <li key={m.id} className="flex items-center gap-2">
                <span className="flex-1">{m.content}</span>
                <button type="button" onClick={() => onFeedback(m.id, "helpful")} aria-label={`This note is right: ${m.content}`} className="muna-btn !min-h-8 !px-2.5 !py-1">Right</button>
                <button type="button" onClick={() => onFeedback(m.id, "wrong")} aria-label={`This note is wrong: ${m.content}`} className="muna-btn !min-h-8 !px-2.5 !py-1">Wrong</button>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

/* ---------- settings sheet ---------- */
function Toggle({ checked, onChange, children }) {
  return (
    <label className="flex min-h-11 items-center gap-3">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="h-5 w-5" style={{ accentColor: "var(--accent)" }} />
      <span>{children}</span>
    </label>
  );
}

function SettingsSheet({ open, onClose, theme, setTheme, memoryOn, setMemoryOn, showEnglish, setShowEnglish, notes, onShowNotes, onCloseNotes, onForget }) {
  const closeRef = useRef(null);
  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-30 flex items-end justify-center bg-black/30 sm:items-center" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label="Settings" onClick={(e) => e.stopPropagation()}
        className="muna-card max-h-[88vh] w-full max-w-[480px] space-y-4 overflow-y-auto rounded-b-none p-6 sm:rounded-b-3xl">
        <div className="flex items-center justify-between">
          <h2 className="muna-heading">Settings</h2>
          <button ref={closeRef} type="button" onClick={onClose} className="muna-btn">Close</button>
        </div>

        <fieldset>
          <legend className="mb-1 text-sm font-semibold" style={{ color: "var(--heading)" }}>Colours</legend>
          <div className="flex gap-2">
            {[["sage", "Sage"], ["sky", "Sky"]].map(([id, label]) => (
              <button key={id} type="button" aria-pressed={theme === id} onClick={() => setTheme(id)}
                className="muna-btn" style={theme === id ? { background: "var(--accent)", color: "#fff" } : undefined}>{label}</button>
            ))}
          </div>
        </fieldset>

        <Toggle checked={showEnglish} onChange={setShowEnglish}>Show English under Lamnso</Toggle>
        <div>
          <Toggle checked={memoryOn} onChange={setMemoryOn}>Remember what helps me between visits</Toggle>
          <p className="pl-8 text-xs opacity-90">
            When on, after a normal reply I save one or two short, anonymous notes. Never your exact words, and never anything from a crisis message.
            Turn it off any time.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={onShowNotes} className="muna-btn">What do you remember?</button>
          <button type="button" onClick={onForget} className="muna-btn muna-btn-danger">Forget me</button>
        </div>

        {notes && (
          <section aria-label="Remembered notes" className="rounded-2xl p-3 text-sm" style={{ background: "var(--pill-bg)" }}>
            <div className="mb-1 flex items-center justify-between">
              <h3 className="font-semibold" style={{ color: "var(--heading)" }}>What I remember about you</h3>
              <button type="button" onClick={onCloseNotes} className="muna-link text-xs">Hide</button>
            </div>
            {notes.length === 0 ? <p>Nothing yet.</p> : <ul className="list-disc space-y-1 pl-5">{notes.map((n) => <li key={n.id}>{n.content}</li>)}</ul>}
          </section>
        )}

        <p className="text-xs opacity-90">
          {APP_NAME} is an AI companion, not a substitute for professional care. Replies are written in English and translated into Lamnso by a
          machine model, so the English is always available. <Link href="/help" className="muna-link">Help and information</Link>
        </p>
      </div>
    </div>
  );
}

/* ---------- page ---------- */
export default function Home() {
  const [ready, setReady] = useState(false);
  const [splash, setSplash] = useState("pending"); // pending | show | done
  const [userId, setUserId] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [theme, setThemeState] = useState("sage");
  const [memoryOn, setMemoryOnState] = useState(false);
  const [showEnglish, setShowEnglishState] = useState(true);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notes, setNotes] = useState(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [canDictate, setCanDictate] = useState(false);
  const [listening, setListening] = useState(false);
  const endRef = useRef(null);
  const recRef = useRef(null);

  useEffect(() => {
    let id = readStored("care_user_id", "");
    if (!id) {
      id = newId();
      writeStored("care_user_id", id);
    }
    setUserId(id);
    setSessionId(`s-${newId()}`);
    const t = readStored("care_theme", "sage");
    setThemeState(t);
    document.documentElement.dataset.theme = t;
    setMemoryOnState(readStored("care_memory", "0") === "1");
    setShowEnglishState(readStored("care_show_english", "1") === "1");
    setCanDictate(Boolean(window.SpeechRecognition || window.webkitSpeechRecognition));
    setSplash(readSession("muna_splash_seen") === "1" ? "done" : "show");
    setReady(true);
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);

  const finishSplash = useCallback(() => {
    writeSession("muna_splash_seen", "1");
    setSplash("done");
  }, []);
  const addMessage = useCallback((m) => setMessages((prev) => [...prev, { id: newId(), ...m }]), []);
  const setTheme = (t) => { setThemeState(t); writeStored("care_theme", t); document.documentElement.dataset.theme = t; };
  const setMemoryOn = (v) => { setMemoryOnState(v); writeStored("care_memory", v ? "1" : "0"); };
  const setShowEnglish = (v) => { setShowEnglishState(v); writeStored("care_show_english", v ? "1" : "0"); };

  async function send(text) {
    const message = (text ?? input).trim();
    if (!message || busy) return;
    recRef.current?.stop();
    setInput("");
    setError("");
    addMessage({ role: "user", text: message });
    setBusy(true);
    try {
      const data = await api("/chat", { message, session_id: sessionId, user_id: userId, remember: memoryOn });
      addMessage({ role: "assistant", data });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
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

  async function showNotes() {
    setError("");
    try {
      setNotes((await api("/memory/export", { user_id: userId })).memories);
    } catch (err) {
      setError(err.message);
      setSheetOpen(false);
    }
  }

  async function forgetAll() {
    if (!window.confirm("Erase everything I remember about you, including mood check-ins? This cannot be undone.")) return;
    setError("");
    try {
      const res = await api("/memory/forget", { user_id: userId });
      setNotes(null);
      setSheetOpen(false);
      const extra = res.checkins_erased === false ? " I could not erase your mood check-ins right now; please try again later." : "";
      addMessage({ role: "system", text: `Done. I erased ${res.erased} note${res.erased === 1 ? "" : "s"} about you.${extra}` });
    } catch (err) {
      setError(err.message);
      setSheetOpen(false);
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

  function toggleDictation() {
    if (listening) {
      recRef.current?.stop();
      return;
    }
    if (readStored("care_voice_ok", "0") !== "1") {
      const ok = window.confirm("Voice input uses your browser's speech service, which may send your voice to the company that makes your browser. Use it?");
      if (!ok) return;
      writeStored("care_voice_ok", "1");
    }
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const rec = new SR();
    rec.lang = "en-US";
    rec.interimResults = true;
    rec.continuous = false;
    rec.onresult = (e) => setInput(Array.from(e.results).map((r) => r[0].transcript).join(" "));
    rec.onend = () => setListening(false);
    rec.onerror = () => { setListening(false); setError("I could not hear you. You can also type your message."); };
    recRef.current = rec;
    setListening(true);
    rec.start();
  }

  const started = messages.length > 0;
  const hasText = input.trim().length > 0;

  if (splash === "pending") return <div className="min-h-screen" aria-hidden="true" />;

  return (
    <>
    {splash === "show" && <Splash onDone={finishSplash} />}
    <div className="mx-auto flex min-h-screen w-full max-w-[480px] flex-col" inert={splash === "show" ? true : undefined} aria-hidden={splash === "show" ? true : undefined}>
      <header className="flex items-center justify-between px-6 pb-4 pt-9">
        <div className="flex items-center gap-2.5">
          <Logo size={36} />
          <h1 className="muna-title">{APP_NAME}</h1>
        </div>
        <div className="flex items-center gap-1">
          {started && (
            <button type="button" onClick={() => { setMessages([]); setError(""); setSessionId(`s-${newId()}`); }} className="muna-btn">New chat</button>
          )}
          <button type="button" onClick={() => setSheetOpen(true)} aria-label="Settings" className="grid h-11 w-11 place-items-center rounded-full" style={{ color: "var(--heading)" }}>
            <GearIcon />
          </button>
        </div>
      </header>

      <main className="flex-1 px-5 pb-44">
        {ready && !started && (
          <section className="muna-card p-6" aria-label={`Meet ${APP_NAME}`}>
            <div className="flex items-center gap-4">
              <Avatar />
              <div>
                <h2 className="muna-heading">Hi, I’m {APP_NAME}</h2>
                <p className="mt-1 text-sm">I’m here to listen, check in on how you feel, and help you take a calm moment.</p>
              </div>
            </div>
            <div className="mt-5 flex flex-col gap-3">
              {SUGGESTIONS.map((s) => (
                <button key={s} type="button" className="muna-pill" onClick={() => send(s)}>{s}</button>
              ))}
            </div>
            <div className="mt-6 border-t pt-4" style={{ borderColor: "var(--pill-bg)" }}>
              <p className="mb-2 text-sm font-semibold" style={{ color: "var(--heading)" }}>How are you feeling right now?</p>
              <div className="flex items-center gap-2">
                {[1, 2, 3, 4, 5].map((n) => (
                  <button key={n} type="button" className="muna-chip" onClick={() => checkin(n)}
                    aria-label={`Mood ${n} of 5${n === 1 ? ", very low" : n === 5 ? ", good" : ""}`}>{n}</button>
                ))}
              </div>
              <p className="mt-2 text-xs opacity-90">1 is very low, 5 is good. Saved under an anonymous key; “Forget me” erases it.</p>
            </div>
          </section>
        )}

        <section aria-label="Conversation" aria-live="polite" className="flex flex-col gap-4">
          {messages.map((m) =>
            m.role === "user" ? (
              <div key={m.id} className="muna-user ml-auto max-w-[85%] text-[15px]">{m.text}</div>
            ) : m.role === "system" ? (
              <p key={m.id} className="text-center text-xs opacity-90">{m.text}</p>
            ) : (
              <div key={m.id} className="max-w-[94%]">
                <Reply data={m.data} showEnglish={showEnglish} />
                <Meta data={m.data} onFeedback={feedback} />
              </div>
            )
          )}
          {busy && <p className="text-sm opacity-90">Thinking…</p>}
          {error && <p role="alert" className="rounded-2xl bg-red-50 p-3 text-sm text-red-900 ring-1 ring-red-200">{error}</p>}
          <div ref={endRef} />
        </section>
      </main>

      <div className="fixed inset-x-0 bottom-0 z-20">
        <div className="mx-auto w-full max-w-[480px] px-5 pb-6">
          <p className="mb-2 text-center text-[11px] opacity-90">
            {APP_NAME} is an AI companion, not a substitute for professional care. In an emergency, contact your local emergency services.
          </p>
          <form onSubmit={(e) => { e.preventDefault(); send(); }} className="flex items-center gap-3">
            <label htmlFor="msg" className="sr-only">Your message</label>
            <input id="msg" className="muna-input" type="text" value={input} maxLength={2000} autoComplete="off"
              onChange={(e) => setInput(e.target.value)} placeholder={`Tell ${APP_NAME} how you feel...`} />
            {hasText || !canDictate ? (
              <button type="submit" className="muna-fab" aria-label="Send message" disabled={busy || !hasText}><SendIcon /></button>
            ) : (
              <button type="button" className="muna-fab" onClick={toggleDictation} aria-pressed={listening}
                aria-label={listening ? "Stop voice input" : "Speak your message"}><MicIcon /></button>
            )}
          </form>
        </div>
      </div>

      <SettingsSheet open={sheetOpen} onClose={() => setSheetOpen(false)} theme={theme} setTheme={setTheme}
        memoryOn={memoryOn} setMemoryOn={setMemoryOn} showEnglish={showEnglish} setShowEnglish={setShowEnglish}
        notes={notes} onShowNotes={showNotes} onCloseNotes={() => setNotes(null)} onForget={forgetAll} />
    </div>
    </>
  );
}
