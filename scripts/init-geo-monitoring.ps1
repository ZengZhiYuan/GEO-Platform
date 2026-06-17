$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoDir = if ($env:REPO_DIR) { $env:REPO_DIR } else { (Get-Location).Path }

Set-Location $RepoDir

Write-Host "[1/3] 启动 PostgreSQL 与 Redis..."
docker compose up -d postgres redis

Write-Host "[2/3] 等待 PostgreSQL 就绪..."
for ($i = 0; $i -lt 30; $i++) {
    docker compose exec -T postgres pg_isready *> $null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 2
}

Write-Host "[3/3] 执行建表脚本..."
python (Join-Path $ScriptDir "init_geo_monitoring.py")

Write-Host "完成。"
