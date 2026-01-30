param (
    [Parameter(Mandatory=$false)]
    [ValidateSet("dev", "build", "setup", "check")]
    [string]$Action = "dev"
)

$RootDir = Get-Location
# Resolve the local Tauri CLI binary (Windows uses .ps1 or .cmd)
$TauriCli = Join-Path $RootDir "frontend\node_modules\.bin\tauri.ps1"
if (-not (Test-Path $TauriCli)) {
    $TauriCli = Join-Path $RootDir "frontend\node_modules\.bin\tauri.cmd"
}

function Setup-Project {
    Write-Host "`n>>> [1/2] Installing frontend dependencies..." -ForegroundColor Cyan
    Set-Location "$RootDir\frontend"
    npm install
    
    Write-Host "`n>>> [2/2] Verifying Rust environment..." -ForegroundColor Cyan
    Set-Location "$RootDir\src-tauri"
    cargo --version
    
    Set-Location $RootDir
    Write-Host "`n✅ Setup complete!" -ForegroundColor Green
}

function Run-Dev {
    if (-not (Test-Path $TauriCli)) {
        Write-Host "⚠️  Tauri CLI not found. Running setup..." -ForegroundColor Yellow
        Setup-Project
    }
    Write-Host "`n>>> Starting Tauri Development Mode..." -ForegroundColor Cyan
    Write-Host "    Frontend: http://localhost:5173" -ForegroundColor Gray
    # Run from the project root so it finds src-tauri
    & $TauriCli dev
}

function Run-Build {
    if (-not (Test-Path $TauriCli)) {
        Write-Host "⚠️  Tauri CLI not found. Running setup..." -ForegroundColor Yellow
        Setup-Project
    }
    Write-Host "`n>>> Building Production Release..." -ForegroundColor Cyan
    & $TauriCli build
}

function Run-Check {
    Write-Host "`n>>> Running Rust Cargo Check..." -ForegroundColor Cyan
    Set-Location "$RootDir\src-tauri"
    cargo check
    Set-Location $RootDir
}

# --- Execution ---

switch ($Action) {
    "setup" { Setup-Project }
    "dev"   { Run-Dev }
    "build" { Run-Build }
    "check" { Run-Check }
    Default { Run-Dev }
}
