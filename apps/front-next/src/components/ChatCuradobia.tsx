// file: apps/front-next/src/components/ChatCuradobia.tsx
"use client";

import { useEffect, useRef, useState } from "react";
import type { DemoUser } from "@/lib/auth";
import { loadHistory, saveHistory } from "@/lib/history";
import {
  loadInventory,
  searchInventory,
  parseInventoryIntent,
  formatInventoryAnswer,
  type StockItem,
} from "@/lib/inventory";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";

type Msg = {
  id: string;
  role: "user" | "assistant";
  text: string;
  at: number; // timestamp fixo
};

function hhmm(ts: number) {
  return new Date(ts).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

const uuid = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

type Props = {
  user: DemoUser | null;
  onRequestAuth: () => void;
  onLogout: () => void;
};

function initialMsgs(): Msg[] {
  return [
    {
      id: uuid(),
      role: "assistant",
      text:
        "Oi! Eu sou a BIA 😊 Como posso ajudar hoje?\n\n" +
        "Para **salvar seu histórico** e personalizar a experiência, entre na sua conta.",
      at: Date.now(),
    },
  ];
}

function sanitizeHistory(hist: Msg[], user: DemoUser | null): Msg[] {
  const out: Msg[] = [];
  const seen = new Set<string>();
  const needle = "Já encontrei seu perfil";
  for (const m of hist) {
    if (!user && m.role === "assistant" && m.text.includes(needle)) continue;
    const key = `${m.role}|${m.text.trim()}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(m);
  }
  return out;
}

function alreadyGreeted(msgs: Msg[]) {
  const needle = "Já encontrei seu perfil";
  return msgs.some((m) => m.role === "assistant" && m.text.includes(needle));
}

export default function ChatCuradobia({ user, onRequestAuth, onLogout }: Props) {
  // mensagens (histórico)
  const [msgs, setMsgs] = useState<Msg[]>(() => {
    const h = loadHistory(user);
    return h.length ? sanitizeHistory(h, user) : initialMsgs();
  });

  // estoque
  const [stock, setStock] = useState<StockItem[] | null>(null);
  const [stockReady, setStockReady] = useState(false);
  useEffect(() => {
    (async () => {
      try {
        const s = await loadInventory();
        setStock(s);
      } catch {
        setStock(null);
      } finally {
        setStockReady(true);
      }
    })();
  }, []);

  // recarrega histórico ao trocar usuário
  const greetedRef = useRef<string | null>(null);
  useEffect(() => {
    const h = loadHistory(user);
    const fresh = h.length ? sanitizeHistory(h, user) : initialMsgs();
    setMsgs(fresh);
    setIsTyping(false);
    setLoading(false);
    greetedRef.current = null;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.email]);

  // persiste histórico
  useEffect(() => {
    saveHistory(user, msgs);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [msgs, user?.email]);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [isTyping, setIsTyping] = useState(false);

  // scroll
  const scrollRef = useRef<HTMLDivElement>(null);
  const scrollToBottom = (smooth = true) => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: smooth ? "smooth" : "auto" });
  };
  useEffect(() => {
    scrollToBottom(true);
  }, [msgs, loading, isTyping]);

  // SSE
  const esRef = useRef<EventSource | null>(null);
  useEffect(() => {
    return () => {
      esRef.current?.close();
      esRef.current = null;
    };
  }, []);

  // saudação pós-login (sem duplicar)
  useEffect(() => {
    if (user && greetedRef.current !== user.email) {
      greetedRef.current = user.email;
      setMsgs((prev: Msg[]) =>
        alreadyGreeted(prev)
          ? prev
          : [
              ...prev,
              {
                id: uuid(),
                role: "assistant",
                text: `Oi, **${user.name}**! Já encontrei seu perfil. Em que posso ajudar?`,
                at: Date.now(),
              },
            ]
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.email]);

  // INVENTÁRIO → responde antes do backend se a pergunta for de estoque
  async function tryAnswerFromInventory(prompt: string): Promise<string | null> {
    if (!stockReady || !stock) return null;
    const intent = parseInventoryIntent(prompt, stock);
    if (!intent) return null;
    const rows = searchInventory(stock, intent);
    return formatInventoryAnswer(rows, intent);
  }

  async function handleSend(e?: React.FormEvent) {
    e?.preventDefault();
    const prompt = input.trim();
    if (!prompt || loading) return;

    setIsTyping(false);

    const userMsg: Msg = { id: uuid(), role: "user", text: prompt, at: Date.now() };
    setMsgs((prev: Msg[]) => [...prev, userMsg]);

    setInput("");
    setLoading(true);
    setIsTyping(true);
    esRef.current?.close();
    esRef.current = null;

    const delayMs = 3000 + Math.floor(Math.random() * 2000);
    await sleep(delayMs);

    // 1) estoque primeiro
    const invAnswer = await tryAnswerFromInventory(prompt);
    if (invAnswer) {
      setIsTyping(false);
      setMsgs((prev: Msg[]) => [
        ...prev,
        { id: uuid(), role: "assistant", text: invAnswer, at: Date.now() }
      ]);
      setLoading(false);
      setTimeout(() => scrollToBottom(true), 30);
      return;
    }

    // 2) fallback IA
    const aiId = uuid();
    setMsgs((prev: Msg[]) => [...prev, { id: aiId, role: "assistant", text: "", at: Date.now() }]);

    try {
      await new Promise<void>((resolve, reject) => {
        const es = new EventSource(`${API_BASE}/api/stream?prompt=${encodeURIComponent(prompt)}`);
        esRef.current = es;

        es.onmessage = (ev) => {
          const data = ev.data ?? "";
          if (data === "[[DONE]]") {
            setIsTyping(false);
            es.close();
            esRef.current = null;
            resolve();
            return;
          }
          setIsTyping(false);
          setMsgs((prev: Msg[]) => {
            const copy = [...prev];
            const idx = copy.findIndex((x) => x.id === aiId);
            if (idx >= 0) {
              copy[idx] = { ...copy[idx], text: (copy[idx].text ?? "") + data, at: Date.now() };
            }
            return copy;
          });
        };

        es.onerror = () => {
          setIsTyping(false);
          es.close();
          esRef.current = null;
          reject(new Error("SSE error"));
        };
      });
    } catch {
      try {
        const r = await fetch(`${API_BASE}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ prompt }),
        });
        const { reply } = await r.json();
        setIsTyping(false);
        setMsgs((prev: Msg[]) => {
          const copy = [...prev];
          const idx = copy.findIndex((x) => x.id === aiId);
          if (idx >= 0) {
            copy[idx] = { ...copy[idx], text: reply ?? "(sem resposta)", at: Date.now() };
          }
          return copy;
        });
      } catch {
        setIsTyping(false);
        setMsgs((prev: Msg[]) => [
          ...prev,
          { id: uuid(), role: "assistant", text: "Erro ao falar com o servidor.", at: Date.now() }
        ]);
      }
    } finally {
      setIsTyping(false);
      setLoading(false);
      setTimeout(() => scrollToBottom(true), 30);
    }
  }

  const firstAssistantIdx = msgs.findIndex((x) => x.role === "assistant");

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* Barra de sessão (com Sair) */}
      <div className="px-3 py-2 border-b bg-white/60 backdrop-blur text-[12px] text-zinc-600 flex items-center justify-between">
        {user ? (
          <>
            <div>
              Logado como <span className="font-medium text-zinc-800">{user.name}</span>
            </div>
            <button
              onClick={onLogout}
              className="rounded-full border border-zinc-300 px-3 py-1 text-[12px] hover:bg-zinc-50 active:scale-95 transition"
              title="Encerrar sessão"
            >
              Sair
            </button>
          </>
        ) : (
          <>
            <div>
              Você está como convidado.{" "}
              <button onClick={onRequestAuth} className="underline underline-offset-2 hover:no-underline">
                Entrar/Registrar
              </button>{" "}
              para salvar seu histórico.
            </div>
            <div className="w-[60px]" />
          </>
        )}
      </div>

      {/* LISTA */}
      <div ref={scrollRef} className="flex-1 min-h-0 overflow-y-auto overscroll-contain px-3 py-3 space-y-3 bg-white">
        {msgs.map((m, i) => {
          const isUser = m.role === "user";
          if (!m.text) return null;

          return (
            <div key={m.id} className={`flex items-start gap-2 ${isUser ? "justify-end" : "justify-start"}`}>
              {!isUser && (
                <span className="mt-1 inline-flex h-6 w-6 shrink-0 select-none items-center justify-center rounded-full border border-zinc-300 bg-white text-[11px] font-semibold text-zinc-600">
                  C
                </span>
              )}

              <div
                className={`max-w-[85%] rounded-2xl px-4 py-2 text-[13px] leading-relaxed shadow-sm ${
                  isUser ? "self-end bg-zinc-100 text-zinc-900" : "self-start border border-zinc-200 bg-white text-zinc-900"
                }`}
              >
                <div
                  dangerouslySetInnerHTML={{
                    __html: m.text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/\n/g, "<br/>"),
                  }}
                />
                <div suppressHydrationWarning className="mt-1 text-right text-[10px] text-zinc-500">
                  {hhmm(m.at)}
                </div>

                {!isUser && !user && i === firstAssistantIdx && (
                  <div className="mt-2">
                    <button
                      onClick={onRequestAuth}
                      className="rounded-full border border-zinc-300 px-3 py-1 text-[12px] hover:bg-zinc-50 active:scale-95 transition"
                    >
                      Entrar / Registrar
                    </button>
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {isTyping && (
          <div className="flex items-start gap-2 justify-start">
            <span className="mt-1 inline-flex h-6 w-6 shrink-0 select-none items-center justify-center rounded-full border border-zinc-300 bg-white text-[11px] font-semibold text-zinc-600">
              C
            </span>
            <div className="max-w-[85%] rounded-2xl px-4 py-2 text-[13px] leading-relaxed shadow-sm self-start border border-zinc-200 bg-white">
              <div className="typing flex items-center gap-1" aria-live="polite" aria-label="BIA está digitando">
                <span className="dot inline-block h-1.5 w-1.5 rounded-full bg-zinc-500"></span>
                <span className="dot inline-block h-1.5 w-1.5 rounded-full bg-zinc-500"></span>
                <span className="dot inline-block h-1.5 w-1.5 rounded-full bg-zinc-500"></span>
              </div>
            </div>
            <style jsx>{`
              @keyframes blink { 0%{opacity:.25} 20%{opacity:1} 100%{opacity:.25} }
              .typing .dot { animation: blink 1.2s infinite both; }
              .typing .dot:nth-child(2){ animation-delay:.15s }
              .typing .dot:nth-child(3){ animation-delay:.3s }
            `}</style>
          </div>
        )}
      </div>

      {/* INPUT */}
      <form onSubmit={handleSend} className="sticky bottom-0 z-10 shrink-0 border-t bg-white p-2">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Digite sua mensagem..."
            className="flex-1 rounded-full border border-zinc-300 px-4 py-2 text-sm outline-none focus:border-zinc-400"
          />
          <button type="submit" disabled={loading} className="rounded-full bg-black px-4 py-2 text-sm font-medium text-white disabled:opacity-40 transition-transform active:scale-95">
            Enviar
          </button>
        </div>
      </form>
    </div>
  );
}
