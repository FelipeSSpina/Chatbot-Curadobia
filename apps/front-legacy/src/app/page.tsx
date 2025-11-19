/* file: web/src/app/page.tsx */
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
