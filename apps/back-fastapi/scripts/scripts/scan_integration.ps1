$ErrorActionPreference = "Stop"
$root = Get-Location
$debugDir = ".debug"; if (!(Test-Path $debugDir)) { New-Item -ItemType Directory $debugDir | Out-Null }
$out = Join-Path $debugDir "sse_report.txt"
"" | Out-File $out -Encoding utf8
function W($s){ $s | Out-File $out -Append -Encoding utf8 }

W "=== Curadobia — Scanner SSE/Next ==="
W ("Hora: " + (Get-Date -Format s))
W ("Raiz: " + $root + "`r`n")

# -------- BACKEND: server/main.py --------
W "== BACKEND: server/main.py =="
$main = "server\main.py"
if (Test-Path $main) {
  $txt = Get-Content $main -Raw -Encoding UTF8
  W "-> Linhas com EventSourceResponse/gen/yield:"
  Get-ChildItem $main | Select-String -Pattern 'EventSourceResponse|@app.get\("/api/stream"|async def gen|yield\s*\{' -Context 1,2 |
    ForEach-Object { $_.ToString() } | Out-File $out -Append -Encoding utf8

  $hasCharset = $false
  if ($txt -match 'text/event-stream;\s*charset=utf-8') { $hasCharset = $true }
  if ($hasCharset) { W "-> Charset UTF-8 declarado: SIM" } else { W "-> Charset UTF-8 declarado: NÃO (possível mojibake)" }

  $dup = ([regex]::Matches($txt, 'def\s+_safe_call\s*\(')).Count
  if ($dup -gt 1) { W ("-> _safe_call definido #vezes: " + $dup + "  (DUPLICADO)") } else { W ("-> _safe_call definido #vezes: " + $dup) }

  W "`r`n-> Imports relevantes:"
  Get-ChildItem $main | Select-String -Pattern 'from\s+\.autodiscover\s+import\s+load_pipeline|PIPELINE_SPEC|respond_fn' |
    ForEach-Object { $_.ToString() } | Out-File $out -Append -Encoding utf8
} else {
  W "NÃO achei server\main.py"
}

# -------- BACKEND: server/autodiscover.py --------
W "`r`n== BACKEND: server/autodiscover.py =="
$auto = "server\autodiscover.py"
if (Test-Path $auto) {
  $a = Get-Content $auto -Raw -Encoding UTF8
  $wrapOK = $false; if ($a -match 'def\s+wrapper\(.+?\):[\s\S]*def\s+_?\w*\(\s*message\s*:\s*str,\s*\*\*kwargs') { $wrapOK = $true }
  if ($wrapOK) { W "-> wrapper repassa **kwargs: SIM" } else { W "-> wrapper repassa **kwargs: NÃO (pode causar TypeError)" }

  $sigOK = $false; if ($a -match 'def\s+load_pipeline\(') { $sigOK = $true }
  if ($sigOK) { W "-> load_pipeline encontrado (confira assinatura no bloco abaixo)" } else { W "-> load_pipeline ausente" }

  W "`r`n-> Trechos wrapper/load_pipeline:"
  Get-ChildItem $auto | Select-String -Pattern 'def\s+wrapper|def\s+load_pipeline|return\s+wrapper\(|return\s+respond' -Context 1,2 |
    ForEach-Object { $_.ToString() } | Out-File $out -Append -Encoding utf8
} else {
  W "NÃO achei server\autodiscover.py"
}

# -------- FRONTEND --------
W "`r`n== FRONT: procura EventSource e consumo do stream =="
$frontFiles = Get-ChildItem -Path ".\webapp" -Include *.ts,*.tsx,*.js,*.jsx -Recurse -File -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName -notmatch '\\node_modules\\' }

if ($frontFiles -and $frontFiles.Count -gt 0) {
  W "-> Arquivos com EventSource ou /api/stream:"
  $frontFiles | Select-String -Pattern 'new\s+EventSource\s*\(|EventSource\s*\(|/api/stream' -Context 1,2 |
    ForEach-Object { $_.ToString() } | Out-File $out -Append -Encoding utf8

  W "`r`n-> Padrões de setState (concatenação vs substituição):"
  $frontFiles | Select-String -Pattern 'set\w*\s*\(\s*prev\s*=>\s*prev\s*\+\s*ev\.data|set\w*\s*\(\s*ev\.data\s*\)' -Context 0,1 |
    ForEach-Object { $_.ToString() } | Out-File $out -Append -Encoding utf8

  W "`r`n-> Presença de cleanup (.close) e de useRef:"
  $frontFiles | Select-String -Pattern '\.close\s*\(\s*\)|useRef\s*\(' -Context 0,1 |
    ForEach-Object { $_.ToString() } | Out-File $out -Append -Encoding utf8

  W "`r`n-> useEffect que cria EventSource (checar deps [] e cleanup):"
  $frontFiles | Select-String -Pattern 'useEffect\s*\(' -Context 0,3 |
    Where-Object { $_.Line -match 'EventSource\s*\(' -or $_.Context.DisplayPostContext -match 'EventSource\s*\(' } |
    ForEach-Object { $_.ToString() } | Out-File $out -Append -Encoding utf8
} else {
  W "NÃO achei arquivos .ts/.tsx/.js em webapp"
}

# -------- NEXT / StrictMode --------
W "`r`n== NEXT/StrictMode e meta charset =="
$nextCfg = Join-Path "webapp" "next.config.js"
if (Test-Path $nextCfg) {
  $cfg = Get-Content $nextCfg -Raw -Encoding UTF8
  if ($cfg -match 'reactStrictMode\s*:\s*true') { W "-> next.config.js reactStrictMode: true" }
  elseif ($cfg -match 'reactStrictMode\s*:\s*false') { W "-> next.config.js reactStrictMode: false" }
  else { W "-> next.config.js reactStrictMode: (não declarado)" }
  W "   Observação: em dev, StrictMode reexecuta efeitos (pode abrir 2 conexões)."
}

$frontRoots = @(
  "webapp\pages\_app.tsx","webapp\pages\_app.jsx",
  "webapp\pages\_document.tsx","webapp\pages\_document.jsx",
  "webapp\app\layout.tsx","webapp\app\layout.jsx",
  "webapp\app\head.tsx","webapp\app\head.jsx"
)
foreach($f in $frontRoots){
  if (Test-Path $f) {
    W ("`r`n-> " + $f + " (trechos relevantes):")
    Get-ChildItem $f | Select-String -Pattern 'React\.StrictMode|<StrictMode|charSet|charset|<meta' -Context 0,2 |
      ForEach-Object { $_.ToString() } | Out-File $out -Append -Encoding utf8
  }
}

W "`r`n=== FIM ==="
Write-Host "OK: gerei $out" -ForegroundColor Green
