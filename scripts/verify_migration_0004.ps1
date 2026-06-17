# Verify geo_monitoring_0004 migration on an isolated PostgreSQL database.
# Uses docker-compose defaults and NEVER runs downgrade on the main app database.
#
# Prerequisites:
#   1. Docker Desktop is running
#   2. From repo root: docker compose up -d postgres
#
# Usage (repo root):
#   powershell -ExecutionPolicy Bypass -File scripts/verify_migration_0004.ps1

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot "backend\.venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Backend virtualenv not found at $Python"
}

Write-Host "==> Checking Docker..."
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker is not running. Start Docker Desktop, then rerun this script."
}

Write-Host "==> Starting PostgreSQL (docker compose)..."
Push-Location $RepoRoot
try {
    docker compose up -d postgres | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose up failed"
    }

    Write-Host "==> Waiting for PostgreSQL health..."
    $healthy = $false
    for ($i = 0; $i -lt 30; $i++) {
        $status = docker compose ps --format json postgres 2>$null
        if ($status -match '"Health":"healthy"') {
            $healthy = $true
            break
        }
        Start-Sleep -Seconds 2
    }
    if (-not $healthy) {
        throw "PostgreSQL did not become healthy within 60 seconds"
    }

    $env:MIGRATION_TEST_DATABASE_URL = "postgresql+psycopg2://shipu_geo:shipu_geo_password@localhost:5432/geo_migration_test"
    $env:POSTGRES_USER = "shipu_geo"
    $env:POSTGRES_PASSWORD = "shipu_geo_password"

    Write-Host "==> Running offline migration SQL tests..."
    & $Python -m pytest (Join-Path $RepoRoot "backend\tests\test_migrations.py") -q
    if ($LASTEXITCODE -ne 0) { throw "Offline migration tests failed" }

    Write-Host "==> Running PostgreSQL roundtrip integration tests..."
    & $Python -m pytest (Join-Path $RepoRoot "backend\tests\test_migration_roundtrip.py") -q
    if ($LASTEXITCODE -ne 0) { throw "PostgreSQL roundtrip tests failed" }

    Write-Host ""
    Write-Host "[OK] Migration 0004 verified on isolated database geo_migration_test."
    Write-Host "To upgrade your main app database (non-destructive):"
    Write-Host "  cd backend"
    Write-Host "  ..\.venv\Scripts\python.exe -m alembic upgrade head"
    Write-Host ""
    Write-Host "Do NOT run downgrade on shared/production databases unless you have a backup."
}
finally {
    Pop-Location
}
