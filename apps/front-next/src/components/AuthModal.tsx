// file: src/components/AuthModal.tsx
"use client";
// Modal de Login/Registro central, com abas. Registro faz login automático.
// Usa a lib de auth (localStorage). Estilo alinhado ao chat.

import { useState } from "react";
import { DemoUser, login, register, forceSetCurrentUser } from "@/lib/auth";

type Props = {
  open: boolean;
  onClose: () => void;
  onAuth: (user: DemoUser) => void; // chamado após login/registro bem-sucedido
};

export default function AuthModal({ open, onClose, onAuth }: Props) {
  const [tab, setTab] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [pass, setPass] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!open) return null;

  const reset = () => {
    setErr(null);
    setLoading(false);
  };

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setLoading(true);

    try {
      if (tab === "register") {
        if (!name.trim()) throw new Error("Informe seu nome.");
        const u = register(name, email, pass); // cria usuário
        forceSetCurrentUser(u); // loga automaticamente
        onAuth(u);
        onClose();
        return;
      } else {
        const u = login(email, pass);
        onAuth(u);
        onClose();
        return;
      }
    } catch (err: any) {
      setErr(err?.message ?? "Falha inesperada.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 z-[70] bg-black/30 backdrop-blur-[2px] animate-in fade-in duration-150"
        onClick={onClose}
      />
      {/* Modal */}
      <div
        role="dialog"
        aria-modal="true"
        className={[
          "fixed z-[75] inset-0 grid place-items-center px-3",
          "animate-in fade-in-0 zoom-in-95 duration-150",
        ].join(" ")}
      >
        <div className="w-[420px] max-w-[95vw] rounded-2xl border bg-white shadow-2xl overflow-hidden">
          {/* topo */}
          <div className="flex items-center justify-between px-4 py-3 border-b bg-white/70 backdrop-blur">
            <div className="flex items-center gap-2">
              <div className="h-6 w-6 rounded-full border border-zinc-400 text-[10px] font-bold text-zinc-600 grid place-items-center">
                C
              </div>
              <strong className="text-sm">curadobia</strong>
            </div>
            <button
              onClick={onClose}
              className="text-sm text-zinc-700 hover:text-black transition-colors"
            >
              Fechar
            </button>
          </div>

          {/* Abas */}
          <div className="px-4 pt-3">
            <div className="inline-flex rounded-full border p-1 bg-zinc-50">
              <button
                onClick={() => {
                  setTab("login");
                  reset();
                }}
                className={[
                  "px-4 py-1.5 text-sm rounded-full",
                  tab === "login" ? "bg-white shadow-sm" : "text-zinc-600",
                ].join(" ")}
              >
                Entrar
              </button>
              <button
                onClick={() => {
                  setTab("register");
                  reset();
                }}
                className={[
                  "px-4 py-1.5 text-sm rounded-full",
                  tab === "register" ? "bg-white shadow-sm" : "text-zinc-600",
                ].join(" ")}
              >
                Registrar
              </button>
            </div>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="p-4 space-y-3">
            {tab === "register" && (
              <div className="space-y-1">
                <label className="text-xs text-zinc-600">Nome</label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-zinc-400"
                  placeholder="Seu nome"
                />
              </div>
            )}

            <div className="space-y-1">
              <label className="text-xs text-zinc-600">E-mail</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-zinc-400"
                placeholder="voce@email.com"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs text-zinc-600">Senha</label>
              <input
                type="password"
                value={pass}
                onChange={(e) => setPass(e.target.value)}
                className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-zinc-400"
                placeholder="********"
              />
            </div>

            {err && <div className="text-sm text-red-600">{err}</div>}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-full bg-black px-4 py-2 text-sm font-medium text-white disabled:opacity-40 transition-transform active:scale-95 mt-1"
            >
              {tab === "register" ? "Criar minha conta" : "Entrar"}
            </button>

            {tab === "register" && (
              <p className="text-[11px] text-zinc-500 text-center">
                Ao registrar, você será autenticado automaticamente.
              </p>
            )}
          </form>
        </div>
      </div>
    </>
  );
}
