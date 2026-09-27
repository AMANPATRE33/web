<#
.SYNOPSIS
    Manages the local throwaway infrastructure (PostgreSQL + Redis).

.DESCRIPTION
    Neither service needs to be installed system-wide, and neither is shared
    with anything else on the machine:

      * PostgreSQL reuses the binaries already present on the host but writes a
        separate data directory under .local\pgdata on port 55432, with `trust`
        auth. Your existing PostgreSQL instance and its data are never touched.
      * Redis runs from a portable build extracted under .local\redis on 6379.

    Windows caveat: `pg_ctl start` and `redis-server` must outlive the shell
    that launched them, and PostgreSQL's child processes need the `bin`
    directory on PATH or they abort with 0xC0000142. This script solves both by
    launching them through Task Scheduler, which is also why the services keep
    running between commands.

.PARAMETER Action
    start | stop | status | destroy

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/local-services.ps1 start
#>
[CmdletBinding()]
param(
    [ValidateSet('start', 'stop', 'status', 'destroy')]
    [string]$Action = 'start'
)

$ErrorActionPreference = 'Stop'

$RepoRoot    = Split-Path -Parent $PSScriptRoot
$LocalDir    = Join-Path $RepoRoot '.local'
$PgDataDir   = Join-Path $LocalDir 'pgdata'
$PgTaskName  = 'storefront-pg-dev'
$RedisTask   = 'storefront-redis-dev'
$PgPort      = 55432
$RedisPort   = 6379

function Find-PostgresBin {
    $candidates = Get-ChildItem 'C:\Program Files\PostgreSQL' -Directory -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending |
        ForEach-Object { Join-Path $_.FullName 'bin' } |
        Where-Object { Test-Path (Join-Path $_ 'initdb.exe') }
    if (-not $candidates) {
        throw 'PostgreSQL binaries not found. Install PostgreSQL 14+ or point PG_BIN at an existing bin directory.'
    }
    return $candidates[0]
}

function Get-RedisDir {
    $dir = Join-Path $LocalDir 'redis'
    if (-not (Test-Path (Join-Path $dir 'redis-server.exe'))) {
        throw "Portable Redis not found at $dir. Run scripts/fetch-redis.ps1 first."
    }
    return $dir
}

function Invoke-Schtasks {
    param([string]$TaskName, [string]$Command, [switch]$Remove)
    schtasks /delete /tn $TaskName /f 2>&1 | Out-Null
    if ($Remove) { return }
    schtasks /create /tn $TaskName /tr $Command /sc once /st 23:59 /it /f | Out-Null
    schtasks /run /tn $TaskName | Out-Null
}

function Wait-Port {
    param([int]$Port, [int]$TimeoutSeconds = 30)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -WarningAction SilentlyContinue).TcpTestSucceeded {
            return $true
        }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Start-Postgres {
    $pgBin = if ($env:PG_BIN) { $env:PG_BIN } else { Find-PostgresBin }
    New-Item -ItemType Directory -Force -Path $LocalDir | Out-Null

    if (-not (Test-Path (Join-Path $PgDataDir 'PG_VERSION'))) {
        Write-Host "Initialising isolated cluster in $PgDataDir"
        $env:PATH = "$pgBin;$env:PATH"
        & (Join-Path $pgBin 'initdb.exe') -D $PgDataDir -U postgres --auth=trust --encoding=UTF8 --locale=C | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'initdb failed' }

        $bootstrap = Join-Path $LocalDir 'bootstrap-db.sql'
        @'
-- Local development bootstrap. Re-runnable. Dev-only credentials.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'storefront') THEN
        CREATE ROLE storefront LOGIN PASSWORD 'storefront_dev_only';
    END IF;
END
$$;

-- The test suite provisions its own database (`storefront_test`).
ALTER ROLE storefront CREATEDB;

SELECT 'CREATE DATABASE storefront OWNER storefront'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'storefront')\gexec

\connect storefront

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gin;

-- Supabase installs extensions into a dedicated schema and puts it on the
-- search_path. Recreate it so the API's connect hook works identically here.
CREATE SCHEMA IF NOT EXISTS extensions;
GRANT USAGE ON SCHEMA extensions TO storefront;

GRANT ALL ON SCHEMA public TO storefront;
ALTER SCHEMA public OWNER TO storefront;
'@ | Set-Content -Path $bootstrap -Encoding UTF8
    }

    $logDir = Join-Path $LocalDir 'log'
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    $launcher = Join-Path $LocalDir 'start-pg.cmd'
    @"
@echo off
set "PATH=$pgBin;%PATH%"
"$pgBin\postgres.exe" -D "$PgDataDir" -p $PgPort -c listen_addresses=127.0.0.1 -c autovacuum=off -c max_connections=100 > "$logDir\postgres.log" 2>&1
"@ | Set-Content -Path $launcher -Encoding ASCII

    Invoke-Schtasks -TaskName $PgTaskName -Command "`"$launcher`""
    if (Wait-Port -Port $PgPort) {
        Write-Host "PostgreSQL ready on 127.0.0.1:$PgPort" -ForegroundColor Green
    } else {
        throw "PostgreSQL did not open port $PgPort. See $logDir\postgres.log"
    }

    # Apply the bootstrap SQL on a fresh cluster.
    $env:PGPASSWORD = ''
    & (Join-Path $pgBin 'psql.exe') -h 127.0.0.1 -p $PgPort -U postgres -d postgres -q -f (Join-Path $LocalDir 'bootstrap-db.sql') 2>&1 | Out-Null
}

function Start-Redis {
    $redisDir = Get-RedisDir
    $launcher = Join-Path $LocalDir 'start-redis.cmd'
    @"
@echo off
"$redisDir\redis-server.exe" --port $RedisPort --bind 127.0.0.1 --dir "$LocalDir" --dbfilename dev-redis.rdb --appendonly no --save ""
"@ | Set-Content -Path $launcher -Encoding ASCII

    Invoke-Schtasks -TaskName $RedisTask -Command "`"$launcher`""
    if (Wait-Port -Port $RedisPort) {
        Write-Host "Redis ready on 127.0.0.1:$RedisPort" -ForegroundColor Green
    } else {
        throw "Redis did not open port $RedisPort"
    }
}

function Stop-ServiceTask {
    param([string]$TaskName)
    schtasks /end /tn $TaskName 2>&1 | Out-Null
    schtasks /delete /tn $TaskName /f 2>&1 | Out-Null
}

function Show-Status {
    $pgUp = (Test-NetConnection -ComputerName 127.0.0.1 -Port $PgPort -WarningAction SilentlyContinue).TcpTestSucceeded
    $redisUp = (Test-NetConnection -ComputerName 127.0.0.1 -Port $RedisPort -WarningAction SilentlyContinue).TcpTestSucceeded
    Write-Host ("PostgreSQL  127.0.0.1:{0}  {1}" -f $PgPort, $(if ($pgUp) { 'UP' } else { 'DOWN' }))
    Write-Host ("Redis       127.0.0.1:{0}  {1}" -f $RedisPort, $(if ($redisUp) { 'UP' } else { 'DOWN' }))
    Write-Host ""
    Write-Host "API         http://localhost:8000   (cd backend; python -m uvicorn app.main:app --reload)"
    Write-Host "Frontend    http://localhost:3000   (cd frontend; npm run dev)"
    Write-Host "Worker      python -m app.workers    (cd backend)"
}

switch ($Action) {
    'start'   { Start-Postgres; Start-Redis; Show-Status }
    'stop'    { Stop-ServiceTask -TaskName $PgTaskName; Stop-ServiceTask -TaskName $RedisTask; Write-Host 'Stopped.' }
    'status'  { Show-Status }
    'destroy' {
        Stop-ServiceTask -TaskName $PgTaskName
        Stop-ServiceTask -TaskName $RedisTask
        Remove-Item -Recurse -Force $PgDataDir -ErrorAction SilentlyContinue
        Write-Host "Removed $PgDataDir"
    }
}
