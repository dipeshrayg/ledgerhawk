import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";

export function CopilotDrawer() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([
    { role: "assistant", text: "Ask me about vendors, overcharges, clauses, or compliance - I only answer from the Violation Graph, never a guess." },
  ]);
  const [input, setInput] = useState("");
  const [suggested, setSuggested] = useState([]);
  const [sending, setSending] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    api.suggestedQuestions().then((d) => setSuggested(d.questions)).catch(() => {});
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo?.({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, open]);

  async function send(question) {
    const q = question ?? input;
    if (!q.trim() || sending) return;
    setMessages((m) => [...m, { role: "user", text: q }]);
    setInput("");
    setSending(true);
    try {
      const res = await api.copilotAsk(q);
      setMessages((m) => [...m, { role: "assistant", text: res.answer, source: res.source }]);
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", text: `Error: ${e.message}`, source: "error" }]);
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-5 right-5 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-indigo-600 text-white shadow-lg hover:bg-indigo-700 transition"
          aria-label="Open Audit Copilot"
        >
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>
        </button>
      )}

      <div
        className={`fixed bottom-0 right-0 z-30 flex h-full w-full max-w-md transform flex-col border-l border-neutral-200 bg-white shadow-2xl transition-transform dark:border-neutral-800 dark:bg-neutral-900 ${open ? "translate-x-0" : "translate-x-full"}`}
      >
        <div className="flex items-center justify-between border-b border-neutral-200 px-4 py-3 dark:border-neutral-800">
          <div>
            <div className="font-semibold text-neutral-900 dark:text-neutral-50">Audit Copilot</div>
            <div className="text-xs text-neutral-500 dark:text-neutral-400">Grounded in the Violation Graph - F10</div>
          </div>
          <button
            onClick={() => setOpen(false)}
            aria-label="Close Audit Copilot"
            className="rounded-full p-1.5 text-neutral-500 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-800"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>

        <div ref={scrollRef} aria-live="polite" className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
          {messages.map((m, i) => (
            <div key={i} className={`max-w-[90%] rounded-lg px-3 py-2 text-sm whitespace-pre-line ${m.role === "user" ? "ml-auto bg-indigo-600 text-white" : "bg-neutral-100 text-neutral-800 dark:bg-neutral-800 dark:text-neutral-100"}`}>
              {m.text}
            </div>
          ))}
          {sending && <div className="text-xs text-neutral-400">thinking…</div>}
        </div>

        {messages.length <= 1 && (
          <div className="flex flex-wrap gap-1.5 border-t border-neutral-200 px-4 py-2 dark:border-neutral-800">
            {suggested.slice(0, 4).map((q) => (
              <button key={q} onClick={() => send(q)} className="rounded-full border border-neutral-300 px-2.5 py-1 text-xs text-neutral-600 hover:bg-neutral-100 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-800">
                {q}
              </button>
            ))}
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
          className="flex gap-2 border-t border-neutral-200 p-3 dark:border-neutral-800"
        >
          <label htmlFor="copilot-question" className="sr-only">Ask the Audit Copilot a question</label>
          <input
            id="copilot-question"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about vendors, overcharges, clauses…"
            className="flex-1 rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm outline-none focus:border-indigo-500 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100"
          />
          <button type="submit" className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700">
            Ask
          </button>
        </form>
      </div>
    </>
  );
}
