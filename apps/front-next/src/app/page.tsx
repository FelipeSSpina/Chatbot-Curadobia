// src/app/page.tsx
export default function Page() {
  return (
    <main className="w-screen h-screen">
      {/* Site legado em tela cheia */}
      <iframe
        src="/legacy/index.html"
        title="Curadobia (legado)"
        className="fixed inset-0 w-full h-full border-0"
      />
    </main>
  );
}
