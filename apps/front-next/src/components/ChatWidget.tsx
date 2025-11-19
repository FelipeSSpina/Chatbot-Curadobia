// file: apps/front-next/src/components/ChatWidget.tsx
"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import AuthModal from "@/components/AuthModal";
import { DemoUser, getCurrentUser, logout as authLogout } from "@/lib/auth";

// Desliga SSR do ChatCuradobia p/ evitar hydration mismatch por timestamps
const ChatCuradobia = dynamic(() => import("@/components/ChatCuradobia"), {
  ssr: false,
});

export default function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [authOpen, setAuthOpen] = useState(false);
  const [user, setUser] = useState<DemoUser | null>(null);

  // estado inicial do usuário (persistido)
  useEffect(() => {
    setUser(getCurrentUser());
  }, []);

  // abrir/fechar via postMessage (opcional)
  useEffect(() => {
    const onMsg = (ev: MessageEvent) => {
      if (ev?.data?.type === "BIA_OPEN") setOpen(true);
      if (ev?.data?.type === "BIA_CLOSE") setOpen(false);
      if (ev?.data?.type === "BIA_LOGIN") setAuthOpen(true);
    };
    window.addEventListener("message", onMsg);
    return () => window.removeEventListener("message", onMsg);
  }, []);

  // fechar com ESC quando aberto
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      {/* Botão flutuante (toggle) */}
      <button
        onClick={() => setOpen((v) => !v)}
        aria-pressed={open}
        aria-label={open ? "Fechar chat" : "Abrir chat"}
        className={[
          "fixed bottom-4 right-4 z-[60] rounded-full bg-black text-white px-4 py-3 shadow-lg",
          "transition-transform duration-200 ease-out active:scale-95",
          "focus:outline-none focus-visible:ring-2 focus-visible:ring-black/30",
        ].join(" ")}
      >
        {open ? "Fechar BIA" : "BIA • ajuda?"}
      </button>

      {/* Overlay do chat (clicar fora fecha) */}
      <div
        onClick={() => setOpen(false)}
        aria-hidden={!open}
        className={[
          "fixed inset-0 z-40",
          "bg-black/20 backdrop-blur-[1px]",
          "transition-opacity duration-200",
          open ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none",
        ].join(" ")}
      />

      {/* Painel do chat */}
      <div
        role="dialog"
        aria-modal="false"
        aria-label="Chat Curadobia"
        aria-hidden={!open}
        className={[
          "fixed bottom-20 right-4 z-50",
          "w-[380px] max-w-[95vw] h-[520px] max-h-[70vh]",
          "rounded-2xl overflow-hidden border bg-white shadow-2xl",
          "flex flex-col",
          "transform-gpu will-change-transform",
          "transition-all duration-250",
          open
            ? "opacity-100 translate-y-0 scale-100 pointer-events-auto ease-out"
            : "opacity-0 translate-y-3 scale-[0.98] pointer-events-none ease-in",
        ].join(" ")}
        style={{ transitionDuration: "260ms" }}
      >
        {/* Cabeçalho */}
        <div className="flex items-center justify-between px-3 py-2 border-b bg-white/70 backdrop-blur">
          <div className="flex items-center gap-2">
            <div className="h-6 w-6 rounded-full border border-zinc-400 text-[10px] font-bold text-zinc-600 grid place-items-center">
              C
            </div>
            <strong className="text-sm">curadobia</strong>
          </div>
          {/* canto direito limpo */}
          <div className="w-10 h-6" aria-hidden />
        </div>

        {/* ⚠️ min-h-0 para a lista rolar */}
        <div className="flex-1 min-h-0">
          <ChatCuradobia
            user={user}
            onRequestAuth={() => setAuthOpen(true)}
            onLogout={() => {
              authLogout();
              setUser(null);
            }}
          />
        </div>
      </div>

      {/* Modal de Auth */}
      <AuthModal
        open={authOpen}
        onClose={() => setAuthOpen(false)}
        onAuth={(u: DemoUser) => {
          setUser(u);
          setAuthOpen(false);
        }}
      />
    </>
  );
}
