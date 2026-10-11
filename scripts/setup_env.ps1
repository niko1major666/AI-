# ai-skill-gap environment setup (ASCII only to avoid PS5.1 encoding issues)
# Creates a Python 3.12 venv on the project drive, installs deps,
# and keeps all heavy caches INSIDE the project (delete project = free disk).
$ErrorActionPreference = "Stop"
$UV    = "C:\Users\QWB20\.local\bin\uv.exe"
$Root  = Split-Path -Parent $PSScriptRoot
$Venv  = Join-Path $Root ".venv"
$Req   = Join-Path $Root "requirements.txt"
$Models = Join-Path $Root "models"

if (-not (Test-Path $UV)) { throw "uv not found at $UV. Install uv first." }

Write-Host "[1/5] Creating Python 3.12 venv ..."
if (Test-Path $Venv) { Remove-Item -Recurse -Force $Venv }
& $UV venv --python 3.12 $Venv
if ($LASTEXITCODE -ne 0) { throw "venv creation failed" }

# Keep all heavy caches inside the project
$env:UV_CACHE_DIR       = Join-Path $Models "uv_cache"
$env:HF_HOME            = Join-Path $Models "hf_cache"
$env:MODELSCOPE_CACHE   = Join-Path $Models "ms_cache"
$env:TRANSFORMERS_CACHE = Join-Path $Models "hf_cache"
$env:HF_ENDPOINT        = "https://hf-mirror.com"

Write-Host "[2/5] Creating cache dirs ..."
foreach ($d in @("uv_cache", "hf_cache", "ms_cache")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $Models $d) | Out-Null
}

Write-Host "[3/5] Installing dependencies (tsinghua mirror) ..."
$Py = Join-Path $Venv "Scripts\python.exe"
& $UV pip install --python $Py -r $Req `
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple `
    --extra-index-url https://pypi.org/simple
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

Write-Host "[4/5] Persisting cache env vars to venv activate script ..."
Add-Content -Path (Join-Path $Venv "Scripts\activate") -Value @"

set UV_CACHE_DIR=$env:UV_CACHE_DIR
set HF_HOME=$env:HF_HOME
set MODELSCOPE_CACHE=$env:MODELSCOPE_CACHE
set HF_ENDPOINT=$env:HF_ENDPOINT
"@

Write-Host "[5/5] Health check ..."
& $Py (Join-Path $Root "scripts\check_env.py")

Write-Host "DONE. Activate with: .venv\Scripts\activate"
