# file: scripts/collect_curadobia_info.ps1
# Coleta e imprime (console + arquivo) os arquivos-chave do Next.js + FastAPI para diagnóstico.

$ErrorActionPreference = 'SilentlyContinue'
$PSStyle.OutputRendering = 'PlainText'

function Write-Header($title) {
  $line = ('=' * ($title.Length + 2))
  "`n$line`n $title`n$line`n"
}

function Write-Sub($title) {
  "`n--- $title ---`n"
}

function Show-File($path) {
  if (Test-Path $path) {
    $full = (Resolve-Path $path).Path
    $rel  = $full.Replace((Get-Location).Path + '\','')
    ">>> BEGIN FILE: $rel"
    $i=1
    Get-Content -LiteralPath $full -ErrorAction SilentlyContinue | ForEach-Object { "{0,6}: {1}" -f $i++, $_ }
    "<<< END FILE: $rel`n"
  }
}

function First-Existing([string[]]$candidates) {
  foreach ($c in $candidates) { if (Test-Path $c) { return $c } }
  return $null
}

function Find-NextRoot($repoRoot) {
  $pkgs = Get-ChildItem -LiteralPath $repoRoot -Recurse -Filter package.json -Force -ErrorAction SilentlyContinue
  foreach ($p in $pkgs) {
    $txt = Get-Content -LiteralPath $p.FullName -Raw -ErrorAction SilentlyContinue
    if ($txt -match '"next"\s*:\s*"') { return (Split-Path -Parent $p.FullName) }
  }
  return $null
}

function Find-BackendRoot($repoRoot) {
  $likely = @(
    Join-Path $repoRoot 'backend'
    Join-Path $repoRoot 'server'
    Join-Path $repoRoot 'api'
  )
  foreach ($p in $likely) { if (Test-Path $p) { return $p } }
  # Se não achou, procura requirements com fastapi
  $reqs = Get-ChildItem -LiteralPath $repoRoot -Recurse -Filter requirements.txt -Force -ErrorAction SilentlyContinue
  foreach ($r in $reqs) {
    $txt = Get-Content -LiteralPath $r.FullName -Raw -ErrorAction SilentlyContinue
    if ($txt -match 'fastapi') { return (Split-Path -Parent $r.FullName) }
  }
  # pyproject com fastapi
  $pys = Get-ChildItem -LiteralPath $repoRoot -Recurse -Filter pyproject.toml -Force -ErrorAction SilentlyContinue
  foreach ($r in $pys) {
    $txt = Get-Content -LiteralPath $r.FullName -Raw -ErrorAction SilentlyContinue
    if ($txt -match 'fastapi') { return (Split-Path -Parent $r.FullName) }
  }
  return $null
}

# 0) repo root via git
$repoRoot = (& git rev-parse --show-toplevel 2>$null)
if (-not $repoRoot) { $repoRoot = (Get-Location).Path }

# prepara saída em arquivo
$outDir = Join-Path $repoRoot 'outputs\debug'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$outFile = Join-Path $outDir 'curadobia_snapshot.txt'
if (Test-Path $outFile) { Remove-Item $outFile -Force }

# coletor: tudo o que for Write-Output também vai para o arquivo
$log = New-Object System.Collections.Generic.List[string]

function Log($text) {
  $log.Add($text)
  $text
}

# 1) Metadados do ambiente
Log (Write-Header "CURADOBIA — SNAPSHOT DE ARQUIVOS (Next.js + FastAPI)")
Log ("Repo root: " + $repoRoot)
$branch = (& git rev-parse --abbrev-ref HEAD 2>$null)
if ($branch) { Log ("Git branch: " + $branch) }
$status = (& git status -sb 2>$null)
if ($status) { Log (Write-Sub "git status -sb"); Log $status }

$nodeVer = (& node -v 2>$null); if ($nodeVer) { Log ("Node: " + $nodeVer) }
$npmVer  = (& npm -v 2>$null);  if ($npmVer)  { Log ("npm: "  + $npmVer) }
$pyVer   = (& python -V 2>$null); if ($pyVer) { Log ("Python: " + $pyVer) }

# 2) FRONTEND (Next)
$nextRoot = Find-NextRoot $repoRoot
if ($nextRoot) {
  Log (Write-Header "NEXT.JS — ROOT: $nextRoot")

  # Estrutura (árvore) resumida
  if (Get-Command tree -ErrorAction SilentlyContinue) {
    Log (Write-Sub "tree (nível 2)"); 
    Log (& cmd /c "tree `"$nextRoot`" /f /a | more")
  }

  # Arquivos principais
  $pkg = Join-Path $nextRoot 'package.json'
  $nextConfig = First-Existing @(
    (Join-Path $nextRoot 'next.config.ts'),
    (Join-Path $nextRoot 'next.config.mjs'),
    (Join-Path $nextRoot 'next.config.js')
  )
  $appLayout = First-Existing @(
    (Join-Path $nextRoot 'app\layout.tsx'),
    (Join-Path $nextRoot 'app\layout.ts'),
    (Join-Path $nextRoot 'app\layout.jsx')
  )
  $appPage = First-Existing @(
    (Join-Path $nextRoot 'app\page.tsx'),
    (Join-Path $nextRoot 'app\page.ts'),
    (Join-Path $nextRoot 'app\page.jsx')
  )
  $pagesApp = First-Existing @(
    (Join-Path $nextRoot 'pages\_app.tsx'),
    (Join-Path $nextRoot 'pages\_app.jsx')
  )
  $pagesIndex = First-Existing @(
    (Join-Path $nextRoot 'pages\index.tsx'),
    (Join-Path $nextRoot 'pages\index.jsx')
  )

  $tailwind = First-Existing @(
    (Join-Path $nextRoot 'tailwind.config.ts'),
    (Join-Path $nextRoot 'tailwind.config.js')
  )
  $postcss = Join-Path $nextRoot 'postcss.config.js'
  $globals = First-Existing @(
    (Join-Path $nextRoot 'styles\globals.css'),
    (Join-Path $nextRoot 'src\styles\globals.css')
  )

  Log (Write-Sub "Arquivos detectados (Next)")

  foreach ($f in @($pkg,$nextConfig,$appLayout,$appPage,$pagesApp,$pagesIndex,$tailwind,$postcss,$globals)) {
    if ($f) { Log (" - " + $f) }
  }

  Log (Write-Sub "Conteúdo (Next)")
  Show-File $pkg       | Tee-Object -FilePath $outFile -Append
  if ($nextConfig) { Show-File $nextConfig | Tee-Object -FilePath $outFile -Append }

  if ($appLayout -or $appPage) {
    Show-File $appLayout | Tee-Object -FilePath $outFile -Append
    Show-File $appPage   | Tee-Object -FilePath $outFile -Append
  } else {
    Show-File $pagesApp  | Tee-Object -FilePath $outFile -Append
    Show-File $pagesIndex| Tee-Object -FilePath $outFile -Append
  }

  Show-File $tailwind | Tee-Object -FilePath $outFile -Append
  Show-File $postcss  | Tee-Object -FilePath $outFile -Append
  Show-File $globals  | Tee-Object -FilePath $outFile -Append

  # Componentes do chat (se existirem)
  $componentsDir = First-Existing @(
    (Join-Path $nextRoot 'components'),
    (Join-Path $nextRoot 'src\components')
  )
  if ($componentsDir -and (Test-Path $componentsDir)) {
    Log (Write-Sub "Procurando componentes de chat em $componentsDir")
    $chatFiles = Get-ChildItem -LiteralPath $componentsDir -Recurse -Include *Chat*.tsx,*Chat*.jsx,*Message*.tsx,*Message*.jsx -ErrorAction SilentlyContinue
    foreach ($cf in $chatFiles) {
      Show-File $cf.FullName | Tee-Object -FilePath $outFile -Append
    }
  }

  # API Routes / Route Handlers (BFF)
  $apiDir = First-Existing @(
    (Join-Path $nextRoot 'app\api'),
    (Join-Path $nextRoot 'pages\api')
  )
  if ($apiDir -and (Test-Path $apiDir)) {
    Log (Write-Sub "API interna do Next (BFF)")
    $apiFiles = Get-ChildItem -LiteralPath $apiDir -Recurse -Include *.ts,*.tsx,*.js,*.mjs -ErrorAction SilentlyContinue
    foreach ($af in $apiFiles) {
      if ($af.FullName -match 'chat|stream|proxy|route') {
        Show-File $af.FullName | Tee-Object -FilePath $outFile -Append
      }
    }
  }
} else {
  Log (Write-Header "NEXT.JS — NÃO DETECTADO (nenhum package.json com dependência \"next\")")
}

# 3) BACKEND (FastAPI)
$backendRoot = Find-BackendRoot $repoRoot
if ($backendRoot) {
  Log (Write-Header "FASTAPI — ROOT: $backendRoot")

  if (Get-Command tree -ErrorAction SilentlyContinue) {
    Log (Write-Sub "tree (nível 2)"); 
    Log (& cmd /c "tree `"$backendRoot`" /f /a | more")
  }

  $mainCandidates = @(
    (Join-Path $backendRoot 'app\main.py'),
    (Join-Path $backendRoot 'main.py')
  )
  $mainPy = First-Existing $mainCandidates

  $routersChat = First-Existing @(
    (Join-Path $backendRoot 'app\routers\chat.py'),
    (Join-Path $backendRoot 'routers\chat.py')
  )
  $schemas = First-Existing @(
    (Join-Path $backendRoot 'app\schemas.py'),
    (Join-Path $backendRoot 'schemas.py')
  )
  $servicesDir = First-Existing @(
    (Join-Path $backendRoot 'app\services'),
    (Join-Path $backendRoot 'services')
  )
  $configPy = First-Existing @(
    (Join-Path $backendRoot 'app\config.py'),
    (Join-Path $backendRoot 'config.py')
  )
  $requirements = Join-Path $backendRoot 'requirements.txt'
  $envSample = First-Existing @(
    (Join-Path $backendRoot '.env.sample'),
    (Join-Path $backendRoot '.env.example')
  )

  Log (Write-Sub "Arquivos detectados (FastAPI)")
  foreach ($f in @($mainPy,$routersChat,$schemas,$configPy,$requirements,$envSample)) {
    if ($f) { Log (" - " + $f) }
  }

  Log (Write-Sub "Conteúdo (FastAPI)")
  Show-File $mainPy       | Tee-Object -FilePath $outFile -Append
  Show-File $routersChat  | Tee-Object -FilePath $outFile -Append
  Show-File $schemas      | Tee-Object -FilePath $outFile -Append
  Show-File $configPy     | Tee-Object -FilePath $outFile -Append
  Show-File $requirements | Tee-Object -FilePath $outFile -Append
  Show-File $envSample    | Tee-Object -FilePath $outFile -Append

  if ($servicesDir -and (Test-Path $servicesDir)) {
    Log (Write-Sub "Services/*")
    $svc = Get-ChildItem -LiteralPath $servicesDir -Recurse -Include *.py -ErrorAction SilentlyContinue
    foreach ($s in $svc) {
      if ($s.Name -match 'openai|client|provider|llm') {
        Show-File $s.FullName | Tee-Object -FilePath $outFile -Append
      }
    }
  }
} else {
  Log (Write-Header "FASTAPI — NÃO DETECTADO (nenhum requirements/pyproject com 'fastapi')")
}

# 4) SALVAR LOG COMPLETO
# Tudo que foi para o console principal relevante já foi para $outFile via Tee-Object nas seções de conteúdo.
# Agora garantimos que o cabeçalho e os sumários também estejam no arquivo:
$logText = ($log -join "`r`n")
Add-Content -LiteralPath $outFile -Value $logText

"`n*** Snapshot salvo em: $outFile ***`n"
if (Test-Path $outFile) { (Get-Item $outFile).FullName }
