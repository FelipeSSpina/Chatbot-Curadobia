/* file: web/src/components/ChatCuradobia.tsx */
"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import { postChat, streamChat } from "@/lib/api";

type Msg = { role: "user" | "assistant"; content: string };

export default function ChatCuradobia() {
  const [input, setInput] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([
    { role: "assistant", content: "Oi! Eu sou a BIA 😊 Como posso ajudar hoje?" }
  ]);
  const [loading, setLoading] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    boxRef.current?.scrollTo({ top: boxRef.current.scrollHeight, behavior: "smooth" });
  }, [msgs]);

  const canSend = useMemo(() => input.trim().length > 0 && !loading, [input, loading]);

  async function handleSend(e?: React.FormEvent) {
    e?.preventDefault();
    if (!canSend) return;

    const text = input.trim();
    setInput("");
    setMsgs((m) => [...m, { role: "user", content: text }, { role: "assistant", content: "" }]);
    setLoading(true);

    try {
      await streamChat(text, (token) => {
        setMsgs((m) => {
          const last = m[m.length - 1];
          const head = m.slice(0, -1);
          return [...head, { ...last, content: last.content + (last.content ? " " : "") + token }];
        });
      });
    } catch {
      const resp = await postChat(text);
      setMsgs((m) => {
        const last = m[m.length - 1];
        const head = m.slice(0, -1);
        return [...head, { ...last, content: resp.reply }];
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col">
      <div ref={boxRef} className="h-[60vh] overflow-y-auto p-4 sm:p-6 bg-brand-bg2/40 rounded-t-2xl space-y-3">
        {msgs.map((m, i) => (
          <div
            key={i}
            className={clsx(
              "max-w-[85%] px-4 py-3 rounded-2xl text-sm leading-relaxed",
              m.role === "user"
                ? "ml-auto bg-brand-fg text-white rounded-br-sm"
                : "mr-auto bg-white ring-1 ring-black/5 rounded-bl-sm"
            )}
          >
            {m.content}
          </div>
        ))}
      </div>

      <form onSubmit={handleSend} className="p-3 sm:p-4 bg-white rounded-b-2xl border-t border-black/5">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Digite sua mensagem…"
            className="flex-1 px-4 py-3 rounded-xl border border-black/10 focus:outline-none focus:ring-2 focus:ring-black/10"
          />
          <button
            disabled={!canSend}
            className={clsx(
              "px-5 py-3 rounded-xl font-medium transition",
              canSend ? "bg-brand-fg text-white hover:opacity-90" : "bg-black/10 text-black/40 cursor-not-allowed"
            )}
          >
            Enviar
          </button>
        </div>
        {loading && <p className="mt-2 text-xs opacity-70">BIA digitando…</p>}
      </form>
    </div>
  );
}
