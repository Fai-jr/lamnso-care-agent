"use client";

import { useState, useRef, useEffect } from "react";
import axios from "axios";
import Link from "next/link";

const API_URL = "http://localhost:8000/api/chat/";
const TTS_URL = "http://localhost:8000/api/tts/";

// Generate a stable per-session sender ID so Rasa can track
// conversation context across multiple messages
function getSenderId() {
  if (typeof window === "undefined") return "anonymous";
  let id = window.sessionStorage.getItem("lamnso_sender_id");
  if (!id) {
    id = "user_" + Math.random().toString(36).slice(2, 11);
    window.sessionStorage.setItem("lamnso_sender_id", id);
  }
  return id;
}

export default function Home() {
  const [messages, setMessages] = useState([
    {
      role: "bot",
      text: "Wìy ó fèn, é wòsò súŋnín. À dzə̀ kitávín á?",
      translation: "Please come, let's talk. Are you well?",
    },
  ]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState(null);
  const scrollRef = useRef(null);
  const senderIdRef = useRef(null);

  useEffect(() => {
    senderIdRef.current = getSenderId();
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, isSending]);

  async function handleSend() {
    const text = input.trim();
    if (!text || isSending) return;

    setError(null);
    setMessages((prev) => [...prev, { role: "user", text }]);
    setInput("");
    setIsSending(true);

    try {
      const response = await axios.post(API_URL, {
        message: text,
        sender_id: senderIdRef.current,
      });

      const { detected_language, translated_input, bot_responses } =
        response.data;

      const botMessages = (bot_responses || []).map((r) => ({
        role: "bot",
        text: r,
      }));

      setMessages((prev) => [
        ...prev,
        ...(detected_language === "english"
          ? [
              {
                role: "system",
                text: `Translated to Lamnso: "${translated_input}"`,
              },
            ]
          : []),
        ...botMessages,
      ]);
    } catch (err) {
      setError(
        "Could not reach the chatbot. Please check your connection and try again."
      );
    } finally {
      setIsSending(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-[#F7F1E8]">
      {/* Header */}
      <header className="border-b border-[#D8C9AE] bg-[#3A2E26] px-6 py-5 sm:px-10">
        <div className="mx-auto flex max-w-3xl items-center justify-between">
          <div>
            <h1 className="font-serif text-2xl tracking-tight text-[#F7F1E8]">
              Muna
            </h1>
            <p className="mt-0.5 text-sm text-[#C9B79C]">
              Someone to talk to, anytime.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/help"
              className="text-sm text-[#E8DCC8] underline-offset-4 transition-colors hover:text-white hover:underline"
            >
              Get help
            </Link>
            <div className="flex items-center gap-2 rounded-full bg-[#4A3B30] px-3 py-1.5">
              <span className="h-2 w-2 rounded-full bg-[#9CB380]" />
              <span className="text-xs text-[#E8DCC8]">Private &amp; confidential</span>
            </div>
          </div>
        </div>
      </header>

      {/* Chat area */}
      <main className="flex flex-1 justify-center px-4 py-6 sm:px-6">
        <div className="flex w-full max-w-3xl flex-col">
          <div
            ref={scrollRef}
            className="flex-1 space-y-4 overflow-y-auto rounded-2xl border border-[#E2D4BC] bg-white/60 p-4 sm:p-6"
            style={{ maxHeight: "calc(100vh - 230px)", minHeight: "60vh" }}
          >
            {messages.map((msg, i) => (
              <MessageBubble key={i} message={msg} />
            ))}

            {isSending && (
              <div className="flex items-center gap-2 pl-1">
                <span className="flex gap-1">
                  <Dot delay="0ms" />
                  <Dot delay="150ms" />
                  <Dot delay="300ms" />
                </span>
                <span className="text-sm text-[#8A7A63]">Muna is thinking…</span>
              </div>
            )}
          </div>

          {error && (
            <p className="mt-3 rounded-lg bg-[#F4DCD3] px-4 py-2 text-sm text-[#7A3B2E]">
              {error}
            </p>
          )}

          {/* Input bar */}
          <div className="mt-4 flex items-end gap-3">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type in Lamnso or English…"
              rows={1}
              className="flex-1 resize-none rounded-xl border border-[#D8C9AE] bg-white px-4 py-3 text-[#3A2E26] placeholder:text-[#A99A82] focus:border-[#8C6D4F] focus:outline-none focus:ring-2 focus:ring-[#8C6D4F]/30"
            />
            <button
              onClick={handleSend}
              disabled={isSending || !input.trim()}
              className="rounded-xl bg-[#8C6D4F] px-5 py-3 font-medium text-white transition-colors hover:bg-[#74573D] disabled:cursor-not-allowed disabled:opacity-40"
            >
              Send
            </button>
          </div>

          <p className="mt-3 text-center text-xs text-[#A99A82]">
            If you are in danger right now, please reach out to someone you trust, or{" "}
            <Link href="/help" className="underline hover:text-[#8C6D4F]">
              see who else can help
            </Link>
            .
          </p>
        </div>
      </main>
    </div>
  );
}

function MessageBubble({ message }) {
  if (message.role === "system") {
    return (
      <p className="px-2 text-center text-xs italic text-[#A99A82]">
        {message.text}
      </p>
    );
  }

  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 text-[15px] leading-relaxed ${
          isUser
            ? "bg-[#8C6D4F] text-white"
            : "bg-[#EFE6D4] text-[#3A2E26]"
        }`}
      >
        {message.text}
        {/* Voice playback: bot bubbles only (skip user + system lines) */}
        {message.role === "bot" && <PlayVoiceButton text={message.text} />}
      </div>
    </div>
  );
}

// On-demand voice playback for a single bot message.
// - Synthesis is slow (~30s on CPU), so audio is generated only on click,
//   never automatically.
// - The generated audio is cached per bubble, so replaying is instant.
// - Failures are non-fatal: the chat keeps working without voice.
function PlayVoiceButton({ text }) {
  const [status, setStatus] = useState("idle"); // idle | loading | playing | error
  const audioUrlRef = useRef(null);
  const audioRef = useRef(null);

  useEffect(() => {
    // Clean up the blob URL and any playing audio when unmounting.
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
      }
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
      }
    };
  }, []);

  function playFrom(url) {
    const audio = new Audio(url);
    audioRef.current = audio;
    audio.onended = () => setStatus("idle");
    audio.onerror = () => setStatus("error");
    audio
      .play()
      .then(() => setStatus("playing"))
      .catch(() => setStatus("error"));
  }

  async function handleClick() {
    // If currently playing, stop.
    if (status === "playing" && audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      setStatus("idle");
      return;
    }

    // If already generated, replay from cache (instant).
    if (audioUrlRef.current) {
      playFrom(audioUrlRef.current);
      return;
    }

    // Otherwise synthesize via the backend proxy.
    setStatus("loading");
    try {
      const res = await axios.post(
        TTS_URL,
        { text },
        { responseType: "blob", timeout: 200000 } // generous: cold CPU synth is slow
      );
      const url = URL.createObjectURL(res.data);
      audioUrlRef.current = url;
      playFrom(url);
    } catch (err) {
      setStatus("error");
    }
  }

  const label =
    status === "loading"
      ? "Generating voice…"
      : status === "playing"
      ? "Stop"
      : status === "error"
      ? "Try again"
      : "Play voice";

  return (
    <div className="mt-2 flex items-center gap-2">
      <button
        onClick={handleClick}
        disabled={status === "loading"}
        className="inline-flex items-center gap-1.5 rounded-full border border-[#D8C9AE] bg-white/70 px-3 py-1 text-xs font-medium text-[#6B5743] transition-colors hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
      >
        {status === "loading" ? (
          <Spinner />
        ) : status === "playing" ? (
          <StopIcon />
        ) : (
          <PlayIcon />
        )}
        {label}
      </button>
      {status === "error" && (
        <span className="text-xs text-[#9A6B5A]">Voice unavailable</span>
      )}
    </div>
  );
}

function PlayIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 12 12" fill="currentColor" aria-hidden="true">
      <path d="M2 1.5v9l8-4.5z" />
    </svg>
  );
}

function StopIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 12 12" fill="currentColor" aria-hidden="true">
      <rect x="2" y="2" width="8" height="8" rx="1" />
    </svg>
  );
}

function Spinner() {
  return (
    <span className="h-3 w-3 animate-spin rounded-full border-2 border-[#C9B79C] border-t-[#6B5743]" />
  );
}

function Dot({ delay }) {
  return (
    <span
      className="h-2 w-2 animate-bounce rounded-full bg-[#8C6D4F]"
      style={{ animationDelay: delay }}
    />
  );
}
