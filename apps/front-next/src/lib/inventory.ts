// file: apps/front-next/src/lib/inventory.ts
export type StockItem = {
  marca: string;
  sku: string;
  nome: string;
  tamanho: string;
  quantidade: number;
};

let cache: StockItem[] | null = null;

export async function loadInventory(): Promise<StockItem[]> {
  if (cache) return cache;
  const res = await fetch("/data/estoque.json", { cache: "no-store" });
  if (!res.ok) throw new Error("Falha ao carregar estoque.");
  const data = (await res.json()) as StockItem[];
  // normaliza campos
  cache = data.map((d) => ({
    marca: d.marca.trim(),
    sku: d.sku.trim(),
    nome: d.nome.trim(),
    tamanho: d.tamanho.trim().toUpperCase(),
    quantidade: Number(d.quantidade || 0),
  }));
  return cache;
}

// Busca simples e tolerante
export type InventoryQuery = {
  q?: string;          // termos do produto (ex.: "blusa molona")
  marca?: string;      // ex.: "Angela Motta"
  tamanho?: string;    // ex.: "M", "T3", "42-44", "U", "38"
};

export function searchInventory(items: StockItem[], query: InventoryQuery): StockItem[] {
  const q = (query.q || "").toLowerCase().normalize("NFD").replace(/\p{Diacritic}/gu, "");
  const marca = (query.marca || "").toLowerCase();
  const tamanho = (query.tamanho || "").toUpperCase();

  return items.filter((it) => {
    const nomeN = it.nome.toLowerCase().normalize("NFD").replace(/\p{Diacritic}/gu, "");
    const okMarca = !marca || it.marca.toLowerCase().includes(marca);
    const okNome =
      !q ||
      q
        .split(/\s+/)
        .filter(Boolean)
        .every((tok) => nomeN.includes(tok));
    const okTam = !tamanho || it.tamanho === tamanho;
    return okMarca && okNome && okTam && it.quantidade > 0;
  });
}

// tenta extrair intenção de estoque do texto natural
export function parseInventoryIntent(prompt: string, allItems: StockItem[]) {
  const p = prompt.toLowerCase();

  const isEstoqueIntent = /(tem|estoque|dispon[ií]vel|tamanho|possui|rolam|temos)\b/.test(p);
  if (!isEstoqueIntent) return null;

  // tenta achar tamanho
  const sizeAliases: Record<string, string> = {
    pp: "PP",
    p: "P",
    m: "M",
    g: "G",
    gg: "GG",
    u: "U",
    t1: "T1",
    t2: "T2",
    t3: "T3",
    t4: "T4",
    t5: "T5",
  };

  let tamanho: string | undefined;
  // ex.: "42-44" ou números isolados
  const mRange = p.match(/\b(\d{2}\s*-\s*\d{2})\b/);
  if (mRange) tamanho = mRange[1].replace(/\s+/g, "");
  if (!tamanho) {
    const mNum = p.match(/\b(3[0-9]|4[0-9])\b/);
    if (mNum) tamanho = mNum[1];
  }
  if (!tamanho) {
    const mAlias = p.match(/\b(pp|gg|t[1-5]|[pmg]|u)\b/);
    if (mAlias) tamanho = sizeAliases[mAlias[1]];
  }

  // tenta achar marca (varre marcas do dataset)
  const marcas = Array.from(new Set(allItems.map((i) => i.marca.toLowerCase()))).sort((a, b) => b.length - a.length);
  const marcaHit = marcas.find((mk) => p.includes(mk));
  const marca = marcaHit ? marcaHit : undefined;

  // termo do produto: remove palavras comuns, tamanho, marca
  let cleaned = p
    .replace(/[?!.;,]/g, " ")
    .replace(/\b(tem|estoque|dispon[ií]vel|qual|quais|tamanhos?|de|da|do|no|na|para|pra|uma|um|o|a|os|as|por|favor)\b/g, " ");
  if (marca) cleaned = cleaned.replace(new RegExp(marca, "g"), " ");
  if (tamanho) cleaned = cleaned.replace(new RegExp(tamanho.toLowerCase(), "g"), " ");
  cleaned = cleaned.replace(/\s+/g, " ").trim();

  // Heurística: se sobrar pouco, deixa vazio (usuário pode ter perguntado só "tem PANTALONA PAH M?")
  if (cleaned.split(" ").length <= 1 && !/\w{3,}/.test(cleaned)) cleaned = "";

  return {
    q: cleaned || undefined,
    marca,
    tamanho,
  } as InventoryQuery;
}

export function formatInventoryAnswer(rows: StockItem[], q: InventoryQuery): string {
  if (!rows.length) {
    let pedaco = q.q ? ` por “${q.q}”` : "";
    if (q.marca) pedaco += pedaco ? ` e marca ${capitalize(q.marca)}` : ` na marca ${capitalize(q.marca)}`;
    if (q.tamanho) pedaco += ` no tamanho ${q.tamanho}`;
    return `Não encontrei itens com estoque${pedaco}. Quer que eu verifique com a equipe?`;
  }

  // agrupa por (marca+nome), listando tamanhos disponíveis
  const key = (r: StockItem) => `${r.marca} :: ${r.nome}`;
  const groups: Record<string, StockItem[]> = {};
  rows.forEach((r) => {
    const k = key(r);
    (groups[k] ||= []).push(r);
  });

  const linhas = Object.entries(groups).map(([k, arr]) => {
    const [marca, nome] = k.split(" :: ");
    const det = arr
      .sort((a, b) => a.tamanho.localeCompare(b.tamanho, undefined, { numeric: true }))
      .map((r) => `${r.tamanho} (${r.quantidade})`)
      .join(", ");
    return `• **${nome}** — ${capitalize(marca)} → ${det}`;
  });

  const header =
    `Achei ${rows.length} variação(ões) com estoque` +
    (q.tamanho ? ` no tamanho ${q.tamanho}` : "") +
    (q.marca ? ` na marca ${capitalize(q.marca)}` : "") +
    (q.q ? ` para “${q.q}”` : "") +
    `:\n\n`;
  return header + linhas.join("\n");
}

function capitalize(s: string) {
  return s.replace(/\b\w/g, (m) => m.toUpperCase());
}
