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
    <#
    .SYNOPSIS
        Returns the path to the newest PostgreSQL bin directory, as a string.

    .DESCRIPTION
        The `@(...)` wrapper is load-bearing, and its absence was a real bug.

        A PowerShell pipeline that yields exactly ONE item is unrolled to a
        scalar on assignment, so without the wrapper `$candidates` is a *string*
        rather than an array. `$candidates[0]` then performs **character
        indexing** on it and returns `[char]'C'` from `C:\Program Files\...`.

        The result was a generated launcher reading

            set "PATH=C;%PATH%"
            "C\postgres.exe" -D ...

        and PostgreSQL never started, reported as the misleading
        "PostgreSQL did not open port 55432". It only manifests when exactly one
        PostgreSQL install is present, which is why it survived: on a machine with
        two versions the array survives un-unrolled and `[0]` behaves.

        The sort is also version-aware rather than alphabetical. `Sort-Object Name
        -Descending` compares strings, so `psqlODBC` sorts above `18` and a
        hypothetical `9` would sort above `18`. Sorting on the parsed major
        version picks the newest actual install.
    #>
    $candidates = @(
        Get-ChildItem 'C:\Program Files\PostgreSQL' -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^\d+$' } |
            Sort-Object { [int]$_.Name } -Descending |
            ForEach-Object { Join-Path $_.FullName 'bin' } |
            Where-Object { Test-Path (Join-Path $_ 'initdb.exe') }
    )
    if ($candidates.Count -eq 0) {
        throw 'PostgreSQL binaries not found. Install PostgreSQL 14+ or point PG_BIN at an existing bin directory.'
    }
    return [string]$candidates[0]
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

    # Clearing a stale task is deliberate housekeeping, and on a first run the
    # task does not exist at all. That is a *normal* outcome, not a failure - but
    # the script runs with $ErrorActionPreference = 'Stop', and a native command
    # writing to stderr becomes an error record, so an un-tolerated
    # `schtasks /delete` on a missing task aborts the whole script before it can
    # create anything. Cold start failed for exactly that reason.
    #
    # So the preference is relaxed only around these calls, and restored after.
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        schtasks /delete /tn $TaskName /f 2>&1 | Out-Null
        if ($Remove) { return }
        schtasks /create /tn $TaskName /tr $Command /sc once /st 23:59 /it /f | Out-Null
        schtasks /run /tn $TaskName | Out-Null
    }
    finally {
        $ErrorActionPreference = $previous
    }
}

function Test-PortOpen {
    <#
    .SYNOPSIS
        Returns $true if something is listening on a local TCP port.

    .DESCRIPTION
        Uses a raw TcpClient rather than Test-NetConnection, for two reasons.

        1. Correctness. `(Test-NetConnection ...).TcpTestSucceeded` is a
           **parse error** in Windows PowerShell 5.1 - the parenthesised command
           is parsed as a statement and `.TcpTestSucceeded` as a separate one, so
           the script dies with "Missing statement block after if ( condition )".
           This machine has 5.1 and no pwsh, so `local-services.ps1 start` did not
           run at all. Assigning the result to a variable first would also fix the
           parse, but see (2).

        2. Speed. Test-NetConnection takes one to two seconds per call, and
           Wait-Port polls every 500ms, so the startup wait was dominated by
           probing rather than by the database actually coming up. A TcpClient
           connect against localhost either succeeds immediately or is refused
           immediately, which is exactly the answer a readiness check needs.
    #>
    param([Parameter(Mandatory)][int]$Port, [int]$TimeoutMs = 400)
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $connect = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        if (-not $connect.AsyncWaitHandle.WaitOne($TimeoutMs, $false)) {
            return $false
        }
        $client.EndConnect($connect)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }
}

function Wait-Port {
    param([int]$Port, [int]$TimeoutSeconds = 30)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortOpen -Port $Port) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Wait-PostgresReady {
    <#
    .SYNOPSIS
        Blocks until PostgreSQL accepts connections, or the timeout expires.

    .DESCRIPTION
        A TCP port check is not readiness. Postgres opens the socket during
        startup and only begins accepting connections a moment later, so
        `Wait-Port` returns while the server still answers

            FATAL: the database system is starting up

        which made the bootstrap `psql` call fail and - because the script runs
        with $ErrorActionPreference = 'Stop' - aborted the run before Redis was
        even started. `pg_isready` asks the actual question.

        Uses a short per-attempt timeout rather than the default so a hung probe
        cannot consume the whole budget on the first try.

        The 180-second default is not slack for its own sake. If the previous
        process was killed rather than shut down cleanly - which is what
        `Stop-Process -Force` does - the next start has to replay the write-ahead
        log, and on a slow disk that fsync was measured at ~54 s here. Sixty
        seconds turned a legitimate recovery into "never became ready", and then
        the next start had to recover from *that* one too.
    #>
    param([string]$PgBin, [int]$Port, [int]$TimeoutSeconds = 180)
    $isready = Join-Path $PgBin 'pg_isready.exe'
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        & $isready -h 127.0.0.1 -p $Port -t 3 -q 2>$null
        if ($LASTEXITCODE -eq 0) { return $true }
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
    if (-not (Wait-Port -Port $PgPort)) {
        throw "PostgreSQL did not open port $PgPort. See $logDir\postgres.log"
    }
    # The port is open; the server may still be starting. Ask pg_isready before
    # running any SQL against it.
    if (-not (Wait-PostgresReady -PgBin $pgBin -Port $PgPort)) {
        throw ("PostgreSQL opened port $PgPort but never became ready. See $logDir\postgres.log. " +
               "If the log shows 'automatic recovery in progress', the previous process was killed " +
               "rather than shut down, and replaying the write-ahead log can take a minute or more.")
    }
    Write-Host "PostgreSQL ready on 127.0.0.1:$PgPort" -ForegroundColor Green

    # Apply the bootstrap SQL. It is deliberately re-runnable, so on every start
    # after the first it emits harmless `NOTICE ... already exists, skipping`
    # lines - and psql writes NOTICE to stderr. Under $ErrorActionPreference =
    # 'Stop' that aborted the script *after* PostgreSQL was already up, so Redis
    # was never started and a working database was reported as a failed start.
    #
    # The exit code is still checked, so a real SQL error is not swallowed: only
    # the stream routing is relaxed.
    $env:PGPASSWORD = ''
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & (Join-Path $pgBin 'psql.exe') -h 127.0.0.1 -p $PgPort -U postgres -d postgres `
            -q -v ON_ERROR_STOP=1 -f (Join-Path $LocalDir 'bootstrap-db.sql') 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Bootstrap SQL failed. Re-run scripts/local-services.ps1 destroy then start, or apply .local\bootstrap-db.sql by hand."
        }
    }
    finally {
        $ErrorActionPreference = $previous
    }
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
    # Same reasoning as Invoke-Schtasks: ending a task that is not there is the
    # normal case when the services were started some other way, and must not
    # abort a `stop`.
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        schtasks /end /tn $TaskName 2>&1 | Out-Null
        schtasks /delete /tn $TaskName /f 2>&1 | Out-Null
    }
    finally {
        $ErrorActionPreference = $previous
    }
}

function Show-Status {
    $pgUp = Test-PortOpen -Port $PgPort
    $redisUp = Test-PortOpen -Port $RedisPort
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
