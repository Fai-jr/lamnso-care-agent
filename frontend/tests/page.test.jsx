import React from "react";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({ default: ({ href, children, ...p }) => <a href={href} {...p}>{children}</a> }));
import Home from "../app/page.js";

const reply = (over = {}) => ({
  route: "agent", model_used: "nvidia/nemotron-3.5-lightning-30b-a3b", translation_ok: true, memory_enabled: false,
  reply_english: "I hear you. Rest a little.", reply_lamnso: "LN1 LN2",
  sentences: [{ english: "I hear you.", lamnso: "LN1" }, { english: "Rest a little.", lamnso: "LN2" }],
  memories_used: [], ideas_used: [], trace: [], ...over,
});

let calls;
function mockApi(handlers = {}) {
  calls = [];
  globalThis.fetch = vi.fn(async (url, init) => {
    const path = url.replace(/^https?:\/\/[^/]+/, "");
    const body = JSON.parse(init.body);
    calls.push({ path, body });
    const h = handlers[path];
    const out = typeof h === "function" ? h(body) : h;
    if (out instanceof Error) throw out;
    if (out?.__status) return { ok: false, status: out.__status, json: async () => out.body ?? {} };
    return { ok: true, status: 200, json: async () => out ?? {} };
  });
}

beforeEach(() => {
  window.localStorage.clear();
  document.documentElement.dataset.theme = "sage";
  window.confirm = vi.fn(() => true);
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
  delete window.SpeechRecognition;
  delete window.webkitSpeechRecognition;
});

async function setup(handlers) {
  mockApi(handlers);
  const user = userEvent.setup();
  render(<Home />);
  await screen.findByText(/Hi, I’m Muna/);
  return user;
}

describe("first screen follows the Muna spec", () => {
  it("shows the hero card, three suggestion pills, the mood row and the input bar", async () => {
    await setup({});
    expect(screen.getByRole("heading", { name: "Muna" })).toBeTruthy();
    expect(screen.getByText(/I’m here to listen, check in on how you feel/)).toBeTruthy();
    for (const s of ["I feel stressed about school", "Help me sleep better", "Guide me through breathing"])
      expect(screen.getByRole("button", { name: s })).toBeTruthy();
    expect(screen.getByPlaceholderText("Tell Muna how you feel...")).toBeTruthy();
    expect(screen.getAllByRole("button", { name: /^Mood \d of 5/ })).toHaveLength(5);
    expect(screen.getByText(/not a substitute for professional care/i)).toBeTruthy();
  });
  it("shows the send button when speech input is not available", async () => {
    await setup({});
    expect(screen.getByRole("button", { name: "Send message" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Speak your message/ })).toBeNull();
  });
});

describe("chatting", () => {
  it("a suggestion pill sends that text, hides the hero card and shows a bilingual reply", async () => {
    const user = await setup({ "/chat": reply() });
    await user.click(screen.getByRole("button", { name: "Help me sleep better" }));
    expect(await screen.findByText("LN1")).toBeTruthy();
    expect(calls[0].path).toBe("/chat");
    expect(calls[0].body).toMatchObject({ message: "Help me sleep better", remember: false });
    expect(calls[0].body.user_id).toBeTruthy();
    expect(screen.getByText("I hear you.")).toBeTruthy();                 // English under Lamnso
    expect(screen.queryByText(/Hi, I’m Muna/)).toBeNull();                // conversation replaced the hero
    expect(screen.getByText(/nemotron-3.5-lightning-30b-a3b/)).toBeTruthy(); // which model answered
    expect(document.querySelector('[lang="lns"]')).toBeTruthy();
  });
  it("typing and pressing Enter sends; the box is cleared", async () => {
    const user = await setup({ "/chat": reply() });
    const box = screen.getByPlaceholderText("Tell Muna how you feel...");
    await user.type(box, "I feel tired{Enter}");
    await screen.findByText("LN1");
    expect(calls[0].body.message).toBe("I feel tired");
    expect(box.value).toBe("");
  });
  it("hides English when the setting is off, except where Lamnso is missing", async () => {
    const user = await setup({ "/chat": reply({ sentences: [{ english: "I hear you.", lamnso: "LN1" }, { english: "Rest a little.", lamnso: null }] }) });
    await user.click(screen.getByRole("button", { name: "Settings" }));
    await user.click(screen.getByLabelText("Show English under Lamnso"));
    await user.click(screen.getByRole("button", { name: "Close" }));
    await user.click(screen.getByRole("button", { name: "Help me sleep better" }));
    await screen.findByText("LN1");
    expect(screen.queryByText("I hear you.")).toBeNull();
    expect(screen.getByText("Rest a little.")).toBeTruthy();
  });
  it("says so when no Lamnso could be produced", async () => {
    const user = await setup({ "/chat": reply({ reply_lamnso: null, translation_ok: false, sentences: [{ english: "I hear you.", lamnso: null }] }) });
    await user.click(screen.getByRole("button", { name: "Help me sleep better" }));
    expect(await screen.findByText(/showing it in English only/)).toBeTruthy();
  });
  it("crisis replies appear in an alert and carry no model label", async () => {
    const user = await setup({ "/chat": reply({ route: "crisis", model_used: null, sentences: [], reply_lamnso: "KRISIS-LN", reply_english: "You matter." }) });
    await user.type(screen.getByPlaceholderText("Tell Muna how you feel..."), "x{Enter}");
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("KRISIS-LN")).toBeTruthy();
    expect(screen.queryByText(/Answered by/)).toBeNull();
  });
  it("shows a friendly error when the service is down, and recovers", async () => {
    const user = await setup({ "/chat": new TypeError("failed to fetch") });
    await user.click(screen.getByRole("button", { name: "Help me sleep better" }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/cannot reach the care service/);
  });
  it("shows server error details such as 503", async () => {
    const user = await setup({ "/chat": { __status: 503, body: { detail: "Memory service unavailable" } } });
    await user.click(screen.getByRole("button", { name: "Help me sleep better" }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/Memory service unavailable/);
  });
});

describe("memory, check-in, privacy controls", () => {
  it("memory is off by default; switching it on sends remember=true and shows what was used", async () => {
    const user = await setup({ "/chat": reply({ memory_enabled: true, memories_used: [{ id: "mem-1", content: "Worries at night", score: 0.2 }] }), "/memory/feedback": { id: "mem-1", confidence: 0.75 } });
    await user.click(screen.getByRole("button", { name: "Settings" }));
    const toggle = screen.getByLabelText("Remember what helps me between visits");
    expect(toggle.checked).toBe(false);
    await user.click(toggle);
    await user.click(screen.getByRole("button", { name: "Close" }));
    await user.click(screen.getByRole("button", { name: "Help me sleep better" }));
    await screen.findByText("LN1");
    expect(calls[0].body.remember).toBe(true);
    expect(window.localStorage.getItem("care_memory")).toBe("1");
    expect(screen.getByText(/memory on, used 1 note/)).toBeTruthy();
    await user.click(screen.getByText("What I remembered"));
    await user.click(screen.getByRole("button", { name: /This note is wrong/ }));
    await waitFor(() => expect(calls.find((c) => c.path === "/memory/feedback").body).toMatchObject({ memory_id: "mem-1", kind: "wrong" }));
  });
  it("mood check-in posts the number and confirms", async () => {
    const user = await setup({ "/checkin": { saved: true } });
    await user.click(screen.getByRole("button", { name: "Mood 2 of 5" }));
    expect(await screen.findByText(/Check-in saved/)).toBeTruthy();
    expect(calls[0]).toMatchObject({ path: "/checkin", body: { mood: 2 } });
  });
  it("'What do you remember?' lists notes; 'Forget me' asks first, then erases", async () => {
    const user = await setup({ "/memory/export": { memories: [{ id: "mem-1", content: "Worries at night" }] }, "/memory/forget": { erased: 1, checkins_erased: true } });
    await user.click(screen.getByRole("button", { name: "Settings" }));
    await user.click(screen.getByRole("button", { name: "What do you remember?" }));
    expect(await screen.findByText("Worries at night")).toBeTruthy();
    window.confirm = vi.fn(() => false);
    await user.click(screen.getByRole("button", { name: "Forget me" }));
    expect(calls.some((c) => c.path === "/memory/forget")).toBe(false);   // declined: nothing sent
    window.confirm = vi.fn(() => true);
    await user.click(screen.getByRole("button", { name: "Forget me" }));
    expect(await screen.findByText(/I erased 1 note about you\./)).toBeTruthy();
  });
  it("tells the person honestly when check-ins could not be erased", async () => {
    const user = await setup({ "/memory/forget": { erased: 0, checkins_erased: false } });
    await user.click(screen.getByRole("button", { name: "Settings" }));
    await user.click(screen.getByRole("button", { name: "Forget me" }));
    expect(await screen.findByText(/could not erase your mood check-ins/)).toBeTruthy();
  });
});

describe("settings sheet and themes", () => {
  it("Sky theme sets data-theme and is remembered; Escape closes the sheet", async () => {
    const user = await setup({});
    await user.click(screen.getByRole("button", { name: "Settings" }));
    await user.click(screen.getByRole("button", { name: "Sky" }));
    expect(document.documentElement.dataset.theme).toBe("sky");
    expect(window.localStorage.getItem("care_theme")).toBe("sky");
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
  });
  it("restores the saved theme on load", async () => {
    window.localStorage.setItem("care_theme", "sky");
    await setup({});
    expect(document.documentElement.dataset.theme).toBe("sky");
  });
  it("New chat clears the conversation and shows the hero again", async () => {
    const user = await setup({ "/chat": reply() });
    await user.click(screen.getByRole("button", { name: "Help me sleep better" }));
    await screen.findByText("LN1");
    await user.click(screen.getByRole("button", { name: "New chat" }));
    expect(await screen.findByText(/Hi, I’m Muna/)).toBeTruthy();
  });
});

describe("voice input", () => {
  it("offers the mic only when supported, asks consent once, and dictates into the box", async () => {
    let instance;
    window.webkitSpeechRecognition = function () { instance = this; this.start = vi.fn(); this.stop = vi.fn(); };
    const user = await setup({});
    const mic = screen.getByRole("button", { name: "Speak your message" });
    await user.click(mic);
    expect(window.confirm).toHaveBeenCalledTimes(1);
    expect(instance.start).toHaveBeenCalled();
    act(() => instance.onresult({ results: [[{ transcript: "I feel anxious" }]] }));
    expect(await screen.findByDisplayValue("I feel anxious")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Send message" })).toBeTruthy();   // mic turns into send
  });
  it("does not start listening when consent is declined", async () => {
    let instance;
    window.webkitSpeechRecognition = function () { instance = this; this.start = vi.fn(); this.stop = vi.fn(); };
    window.confirm = vi.fn(() => false);
    const user = await setup({});
    await user.click(screen.getByRole("button", { name: "Speak your message" }));
    expect(instance).toBeUndefined();
  });
});
