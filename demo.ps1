#Requires -Version 5.1
<#
.SYNOPSIS
    Regulatory Change Analyzer -- one-command launcher.

.DESCRIPTION
    1. Verifies Docker Desktop is running (PostgreSQL + Redis run in containers).
    2. Creates .env from .env.example if missing; fills in a SECRET_KEY if blank.
    3. Starts db + redis via docker compose and waits for health.
    4. Runs Alembic migrations (upgrades to latest revision).
    5. Opens three named console windows:
         [API]    uvicorn  - FastAPI on :8000
         [Worker] celery   - background task worker
         [UI]     vite dev - React frontend on :5173  (proxies /api -> :8000)
    6. Waits for both :8000 and :5173 to respond.
    7. Opens http://localhost:5173 in the default browser.

.PARAMETER NoMigrate
    Skip the Alembic migration step (use if DB schema is already current).

.PARAMETER NoBuild
    Pass --no-build to docker compose (faster restart when images haven't changed).

.EXAMPLE
    .\demo.ps1                         # full start
    .\demo.ps1 -NoMigrate              # restart without running migrations
    .\demo.ps1 -NoMigrate -NoBuild     # fastest restart
#>

param(
    [switch]$NoMigrate = $false,
    [switch]$NoBuild   = $false
)

$RepoRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
Set-Location $RepoRoot

# ---- Helpers -----------------------------------------------------------------

function Write-Step { param([string]$Msg)
    Write-Host ""
    Write-Host "  >>  $Msg" -ForegroundColor Cyan
}
function Write-Ok   { param([string]$Msg) Write-Host "  OK  $Msg" -ForegroundColor Green  }
function Write-Warn { param([string]$Msg) Write-Host "  !!  $Msg" -ForegroundColor Yellow }
function Write-Fail { param([string]$Msg) Write-Host "  XX  $Msg" -ForegroundColor Red    }

function Exit-Script {
    param([string]$Reason)
    Write-Fail $Reason
    Read-Host "`n  Press Enter to exit"
    exit 1
}

function Wait-Http {
    param([string]$Url, [string]$Label, [int]$MaxAttempts = 40)
    Write-Host "      waiting for $Label ..." -ForegroundColor DarkGray
    for ($i = 1; $i -le $MaxAttempts; $i++) {
        try {
            $r = Invoke-WebRequest -Uri $Url -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
            if ($r.StatusCode -lt 500) { return $true }
        } catch { }
        Write-Host "      attempt $i / $MaxAttempts ..." -ForegroundColor DarkGray
        Start-Sleep 3
    }
    return $false
}

function Open-Window {
    param([string]$Title, [string]$WorkDir, [string]$Cmd)
    # Write to a temp .ps1 file — avoids all command-line quoting issues
    $tmp = [System.IO.Path]::GetTempFileName() -replace '\.tmp$', '.ps1'
    $lines = @(
        "`$host.UI.RawUI.WindowTitle = '$Title'",
        $Cmd
    )
    [System.IO.File]::WriteAllLines($tmp, $lines, [System.Text.Encoding]::UTF8)
    Start-Process powershell -WorkingDirectory $WorkDir `
        -ArgumentList @("-NoProfile", "-NoExit", "-File", $tmp)
}

# ---- Banner ------------------------------------------------------------------

Write-Host ""
Write-Host "  ============================================================" -ForegroundColor DarkCyan
Write-Host "     Regulatory Change Analyzer  --  Demo Launcher            " -ForegroundColor Cyan
Write-Host "     PostgreSQL . Redis . FastAPI . Celery . Vite              " -ForegroundColor DarkCyan
Write-Host "  ============================================================" -ForegroundColor DarkCyan
Write-Host ""

# ---- 1. Check Docker ---------------------------------------------------------

Write-Step "Checking Docker"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Exit-Script "Docker not found. Install Docker Desktop from https://docker.com and retry."
}

docker info 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Exit-Script "Docker daemon is not running. Start Docker Desktop and retry."
}

$clientVer = (docker version --format "{{.Client.Version}}" 2>&1) | Select-Object -First 1
Write-Ok "Docker $clientVer"

docker compose version 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Exit-Script "docker compose plugin not found. Update Docker Desktop to v4.x or later."
}
Write-Ok "docker compose plugin present"

# ---- 2. Check Python venv ----------------------------------------------------

Write-Step "Checking Python virtual environment"

$VenvPy      = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$VenvAlembic = Join-Path $RepoRoot ".venv\Scripts\alembic.exe"
$VenvUvicorn = Join-Path $RepoRoot ".venv\Scripts\uvicorn.exe"
$VenvCelery  = Join-Path $RepoRoot ".venv\Scripts\celery.exe"

if (-not (Test-Path $VenvPy)) {
    Write-Warn ".venv not found. Creating and installing dependencies..."
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { Exit-Script "Failed to create .venv -- is Python 3.11+ on PATH?" }
    & $VenvPy -m pip install --quiet -e .
    if ($LASTEXITCODE -ne 0) { Exit-Script "pip install failed. Check pyproject.toml and network access." }
    Write-Ok ".venv created and packages installed"
} else {
    $pyVer = (& $VenvPy --version 2>&1).ToString().Trim()
    Write-Ok "$pyVer (.venv)"
}

# ---- 3. Check Node / npm -----------------------------------------------------

Write-Step "Checking Node / npm"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Exit-Script "Node.js not found. Install from https://nodejs.org (LTS) and retry."
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Exit-Script "npm not found. Reinstall Node.js and retry."
}

$nodeVer = (node --version 2>&1).ToString().Trim()
$npmVer  = (npm --version 2>&1).ToString().Trim()
Write-Ok "Node $nodeVer  /  npm $npmVer"

$FrontendDir = Join-Path $RepoRoot "frontend"
$NodeModules = Join-Path $FrontendDir "node_modules"

if (-not (Test-Path $NodeModules)) {
    Write-Warn "node_modules missing -- running npm install in frontend/..."
    Push-Location $FrontendDir
    npm install --silent
    if ($LASTEXITCODE -ne 0) { Pop-Location; Exit-Script "npm install failed." }
    Pop-Location
    Write-Ok "npm install complete"
} else {
    Write-Ok "node_modules present"
}

# ---- 4. Prepare .env ---------------------------------------------------------

Write-Step "Preparing .env"

$EnvFile     = Join-Path $RepoRoot ".env"
$ExampleFile = Join-Path $RepoRoot ".env.example"

if (-not (Test-Path $EnvFile)) {
    if (Test-Path $ExampleFile) {
        Copy-Item $ExampleFile $EnvFile
        Write-Warn ".env missing -- copied from .env.example"
    } else {
        Exit-Script ".env and .env.example are both missing from $RepoRoot"
    }
}

# Parse .env into hashtable
$rawLines = Get-Content $EnvFile
$envMap   = @{}
foreach ($line in $rawLines) {
    $t = $line.Trim()
    if ((-not $t) -or $t.StartsWith('#')) { continue }
    if ($t -match '^([^=]+)=(.*)$') {
        $k = $matches[1].Trim()
        $v = $matches[2].Trim()
        if (($v.StartsWith('"') -and $v.EndsWith('"')) -or
            ($v.StartsWith("'") -and $v.EndsWith("'"))) {
            $v = $v.Substring(1, $v.Length - 2)
        }
        $envMap[$k] = $v
    }
}

# Generate SECRET_KEY if still at placeholder
$dirty = $false
$needNewKey = (-not $envMap.ContainsKey('SECRET_KEY')) -or
              [string]::IsNullOrWhiteSpace($envMap['SECRET_KEY']) -or
              ($envMap['SECRET_KEY'] -eq 'change-this-in-production')
if ($needNewKey) {
    $bytes = New-Object byte[] 32
    $rng   = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    $envMap['SECRET_KEY'] = [Convert]::ToBase64String($bytes)
    Write-Warn "SECRET_KEY was default/blank -- generated a new random key"
    $dirty = $true
}

if ($dirty) {
    $written  = @{}
    $outLines = @()
    foreach ($line in $rawLines) {
        $t = $line.Trim()
        if ((-not $t) -or $t.StartsWith('#')) { $outLines += $line; continue }
        if ($t -match '^([^=]+)=') {
            $key = $matches[1].Trim()
            if ($envMap.ContainsKey($key)) {
                $outLines += "$key=$($envMap[$key])"
                $written[$key] = $true
                continue
            }
        }
        $outLines += $line
    }
    foreach ($kv in $envMap.GetEnumerator()) {
        if (-not $written.ContainsKey($kv.Key)) { $outLines += "$($kv.Key)=$($kv.Value)" }
    }
    $outLines | Set-Content $EnvFile -Encoding UTF8
    Write-Ok ".env updated"
} else {
    Write-Ok ".env OK"
}

# Export all vars into this process so child processes inherit them
foreach ($kv in $envMap.GetEnumerator()) {
    [System.Environment]::SetEnvironmentVariable($kv.Key, $kv.Value, 'Process')
}

# ---- 5. Start infrastructure (db + redis) ------------------------------------

Write-Step "Starting PostgreSQL (pgvector) and Redis via Docker Compose"
Write-Host "      First run pulls images (~500 MB). Subsequent starts are instant." -ForegroundColor DarkGray

# Stop any stale containers first so they release their ports
Write-Host "      stopping any stale containers from a previous run ..." -ForegroundColor DarkGray
docker compose stop db redis 2>&1 | Out-Null

if ($NoBuild) {
    docker compose up -d --no-build db redis
} else {
    docker compose up -d db redis
}

if ($LASTEXITCODE -ne 0) {
    Write-Fail "docker compose up failed. See output above."
    Write-Host ""
    Write-Host "  Common causes:" -ForegroundColor Yellow
    Write-Host "  - Port 5432 or 6379 is in use by another process." -ForegroundColor Yellow
    Write-Host "    Run:  netstat -ano | findstr ':5432 :6379'" -ForegroundColor Gray
    Write-Host "    Then: taskkill /PID <pid> /F   (or stop the conflicting service)" -ForegroundColor Gray
    Write-Host "  - A previous run left containers in a broken state." -ForegroundColor Yellow
    Write-Host "    Run:  docker compose down   then re-run .\demo.ps1" -ForegroundColor Gray
    Write-Host ""
    Read-Host "  Press Enter to exit"
    exit 1
}
Write-Ok "Containers started"

# Wait for PostgreSQL
Write-Host "      waiting for PostgreSQL ..." -ForegroundColor DarkGray
$dbReady = $false
for ($i = 1; $i -le 30; $i++) {
    docker compose exec -T db pg_isready -U rca_user -d regulatory_db -q 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { $dbReady = $true; break }
    Write-Host "      db not ready ($i/30) ..." -ForegroundColor DarkGray
    Start-Sleep 3
}
if (-not $dbReady) {
    Write-Warn "PostgreSQL health timeout -- attempting to continue anyway."
} else {
    Write-Ok "PostgreSQL healthy"
}

# Wait for Redis
Write-Host "      waiting for Redis ..." -ForegroundColor DarkGray
$redisReady = $false
for ($i = 1; $i -le 20; $i++) {
    docker compose exec -T redis redis-cli ping 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { $redisReady = $true; break }
    Start-Sleep 2
}
if ($redisReady) { Write-Ok "Redis healthy" } else { Write-Warn "Redis health timeout -- continuing." }

# ---- 6. Alembic migrations ---------------------------------------------------

if (-not $NoMigrate) {
    Write-Step "Running Alembic migrations"
    if (Test-Path $VenvAlembic) {
        & $VenvAlembic upgrade head
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "Alembic returned non-zero. DB may already be up to date (safe to continue)."
        } else {
            Write-Ok "Schema up to date"
        }
    } else {
        Write-Warn "alembic not found in .venv -- skipping migrations."
    }
} else {
    Write-Warn "Migrations skipped (-NoMigrate)"
}

# ---- 7. Start FastAPI (uvicorn) on :8000 -------------------------------------

Write-Step "Starting FastAPI (uvicorn) on :8000"

$apiCmd = "& '$VenvUvicorn' src.api.main:app --host 0.0.0.0 --port 8000 --reload"
Open-Window "[RCA] FastAPI :8000" $RepoRoot $apiCmd

$apiUp = Wait-Http "http://localhost:8000/health" "FastAPI :8000" 40
if ($apiUp) {
    Write-Ok "FastAPI is up  ->  http://localhost:8000"
} else {
    Write-Warn "FastAPI health timeout. Check the [RCA] FastAPI window for errors."
}

# ---- 8. Start Celery worker --------------------------------------------------

Write-Step "Starting Celery worker"

$workerCmd = "& '$VenvCelery' -A src.worker.celery_app worker --loglevel=info"
Open-Window "[RCA] Celery Worker" $RepoRoot $workerCmd
Write-Ok "Celery worker started"

# ---- 9. Start Vite dev server on :5173 ---------------------------------------

Write-Step "Starting Vite dev server on :5173"

$viteCmd = "npm run dev"
Open-Window "[RCA] Vite UI :5173" $FrontendDir $viteCmd

$uiUp = Wait-Http "http://localhost:5173" "Vite :5173" 30
if ($uiUp) {
    Write-Ok "Frontend is up  ->  http://localhost:5173"
} else {
    Write-Warn "Vite health timeout. Check the [RCA] Vite UI window for errors."
}

# ---- 10. Open browser + summary ----------------------------------------------

Start-Process "http://localhost:5173"

$hasKey = -not [string]::IsNullOrWhiteSpace($envMap['ANTHROPIC_API_KEY'])
if ($hasKey) {
    $keyStatus = "configured"
    $keyColor  = "Green"
} else {
    $keyStatus = "NOT SET (Chat / Addendum use fallback mode)"
    $keyColor  = "Yellow"
}

$div = "  " + ("=" * 62)
Write-Host ""
Write-Host $div -ForegroundColor DarkCyan
Write-Host "  Service              URL                                    " -ForegroundColor White
Write-Host $div -ForegroundColor DarkCyan
Write-Host "  Frontend (Vite)      http://localhost:5173                  " -ForegroundColor Green
Write-Host "  FastAPI              http://localhost:8000                  " -ForegroundColor Green
Write-Host "  API Docs (Swagger)   http://localhost:8000/docs             " -ForegroundColor Cyan
Write-Host "  PostgreSQL           localhost:5432  (db: regulatory_db)    " -ForegroundColor DarkGray
Write-Host "  Redis                localhost:6379                         " -ForegroundColor DarkGray
Write-Host $div -ForegroundColor DarkCyan
Write-Host ""
Write-Host "  Anthropic API key    $keyStatus" -ForegroundColor $keyColor
Write-Host ""
Write-Host "  Console windows" -ForegroundColor White
Write-Host "  [RCA] FastAPI :8000  - uvicorn with --reload               " -ForegroundColor Gray
Write-Host "  [RCA] Celery Worker  - background task processor           " -ForegroundColor Gray
Write-Host "  [RCA] Vite UI :5173  - Vite dev server (HMR)              " -ForegroundColor Gray
Write-Host ""
Write-Host "  Useful commands" -ForegroundColor White
Write-Host "  Stop infra      docker compose stop db redis               " -ForegroundColor Gray
Write-Host "  Wipe DB         docker compose down -v                     " -ForegroundColor Gray
Write-Host "  Run migrations  .venv\Scripts\alembic.exe upgrade head     " -ForegroundColor Gray
Write-Host "  Fast restart    .\demo.ps1 -NoMigrate                      " -ForegroundColor Gray
Write-Host $div -ForegroundColor DarkCyan
Write-Host ""
