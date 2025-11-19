# file: scripts/hotfix_front.ps1
$ErrorActionPreference = "Stop"

function Test-Next($dir) {
  $pkg = Join-Path $dir "package.json"
  if (!(Test-Path $pkg)) { return $false }
  try {
    $json = Get-Content $pkg -Raw | ConvertFrom-Json
    return ($json.dependencies -and $json.dependencies.PSObject.Properties.Name -contains "next") -or
           ($json.devDependencies -and $json.devDependencies.PSObject.Properties.Name -contains "next")
  } catch { return $false }
}

function Ensure-Dir($p) { if (!(Test-Path $p)) { New-Item -ItemType Directory -Path $p | Out-Null } }

# 0) Pré-requisitos
foreach ($cmd in @("node","npm","npx")) {
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { throw "$cmd não encontrado no PATH." }
}

# 1) Escolhe diretório do front: web (se já for Next) senão webapp
$Front = if (Test-Next "web") { "web" } elseif (Test-Next "webapp") { "webapp" } else { "webapp" }

# 2) Se não existir projeto Next no $Front, criar um do zero
if (-not (Test-Next $Front)) {
  Write-Host "Inicializando Next.js em '$Front'..." -ForegroundColor Cyan
  npx create-next-app@latest $Front --ts --tailwind --app --src-dir --eslint --import-alias "@/*" --no-git --yes
}

# 3) Garante estrutura
Ensure-Dir (Join-Path $Front "src")
Ensure-Dir (Join-Path $Front "src\app")
Ensure-Dir (Join-Path $Front "src\components")
Ensure-Dir (Join-Path $Front "src\lib")

# 4) Garante configs base (idempotente)
# tailwind.config.ts
@'
import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: { fg: "#000000", text: "#545454", bg: "#E6E3E4", bg2: "#E5DFD2" }
      },
      borderRadius: { xl: "1rem", "2xl": "1.25rem" }
    }
  },
  plugins: []
};
export default config;
'@ | Set-Content -Encoding UTF8 (Join-Path $Front "tailwind.config.ts")

# postcss.config.mjs
@'
export default { plugins: { tailwindcss: {}, autoprefixer: {} } };
'@ | Set-Content -Encoding UTF8 (Join-Path $Front "postcss.config.mjs")

# tsconfig.json (ajusta para app dir + strict bom)
@'
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "es2022"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "noEmit": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["next-env.d.ts", "src/**/*", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
'@ | Set-Content -Encoding UTF8 (Join-Path $Front "tsconfig.json")

# 5) Aplica layout.tsx com next/font (elimina necessidade de @import)
@'
import type { Metadata } from "next";
import "./globals.css";
import { Poppins } from "next/font/google";

const poppins = Poppins({ subsets: ["latin"], weight: ["400","500","600"], display: "swap" });

export const metadata: Metadata = {
  title: "Curadobia — Chat",
  description: "Atendimento com identidade visual própria"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-br">
      <body className={poppins.className}>{children}</body>
    </html>
  );
}
'@ | Set-Content -Encoding UTF8 (Join-Path $Front "src\app\layout.tsx")

# 6) Regrava globals.css sem QUALQUER @import (mata o erro do Turbopack)
@'
@tailwind base;
@tailwind components;
@tailwind utilities;

/* Tokens de marca */
:root {
  --brand-fg: #000000;
  --brand-text: #545454;
  --brand-bg: #E6E3E4;
  --brand-bg2: #E5DFD2;
}

/* A fonte é aplicada via next/font no <body> */
html, body { color: var(--brand-text); }

/* Helpers */
.bg-brand-bg  { background-color: var(--brand-bg);  }
.bg-brand-bg2 { background-color: var(--brand-bg2); }
.text-brand-text { color: var(--brand-text); }
.text-brand-fg   { color: var(--brand-fg); }
'@ | Set-Content -Encoding UTF8 (Join-Path $Front "src\app\globals.css")

# 7) Garante página e componente (se não existirem, cria)
if (!(Test-Path (Join-Path $Front "src\app\page.tsx"))) {
@'
"use client";
import ChatCuradobia from "@/components/ChatCuradobia";

export default function Page() {
  return (
    <main className="min-h-screen bg-brand-bg text-brand-text antialiased">
      <div className="max-w-3xl mx-auto p-4 sm:p-6">
        <header className="mb-4 sm:mb-6">
          <h1 className="text-2xl font-semibold tracking-tight text-brand-fg">BIA — Curadobia</h1>
          <p className="text-sm opacity-80">Atendimento com a sua cara (100% CSS controlado por você)</p>
        </header>
        <section className="bg-white rounded-2xl shadow-sm ring-1 ring-black/5">
          <ChatCuradobia />
        </section>
        <footer className="mt-6 text-xs opacity-70">
          <span>v1 • API: {process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000"}</span>
        </footer>
      </div>
    </main>
  );
}
'@ | Set-Content -Encoding UTF8 (Join-Path $Front "src\app\page.tsx")
}

if (!(Test-Path (Join-Path $Front "src\components\ChatCuradobia.tsx"))) {
@'
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
'@ | Set-Content -Encoding UTF8 (Join-Path $Front "src\components\ChatCuradobia.tsx")
}

# api.ts (só cria se não houver)
if (!(Test-Path (Join-Path $Front "src\lib\api.ts"))) {
@'
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

export async function postChat(message: string) {
  const r = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ message, session_id: "web-session" })
  });
  if (!r.ok) throw new Error("chat failed");
  return r.json() as Promise<{ reply: string }>;
}

export async function streamChat(message: string, onToken: (t: string) => void) {
  const url = new URL(`${API_BASE}/api/stream`);
  url.searchParams.set("message", message);
  url.searchParams.set("session_id", "web-session");

  return await new Promise<void>((resolve, reject) => {
    const es = new EventSource(url.toString());
    es.onmessage = (ev) => { onToken((ev.data || "").trim()); };
    es.addEventListener("done", () => { es.close(); resolve(); });
    es.onerror = () => { es.close(); reject(new Error("sse error")); };
  });
}
'@ | Set-Content -Encoding UTF8 (Join-Path $Front "src\lib\api.ts")
}

# 8) Deps: garante que tudo existe (next/react/types + tailwind)
Push-Location $Front
npm pkg set type="module" | Out-Null
npm i next@latest react@latest react-dom@latest clsx@latest
npm i -D typescript@latest @types/react@latest @types/react-dom@latest @types/node@latest tailwindcss@latest postcss@latest autoprefixer@latest
if (!(Test-Path ".env.local")) { "NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000" | Set-Content -Encoding UTF8 ".env.local" }

# 9) Sobe dev server
Start-Process -WindowStyle Minimized powershell -ArgumentList "cd `"$PWD`"; npm run dev"
Pop-Location

Write-Host "`nFront ativo em '$Front'. Abra: http://localhost:3000 (API: http://127.0.0.1:8000)" -ForegroundColor Green
