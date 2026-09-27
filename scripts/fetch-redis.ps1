<#
.SYNOPSIS
    Downloads the portable Redis build used for local development.

.DESCRIPTION
    Redis is not installed system-wide. This fetches the maintained Windows
    build and extracts it to .local\redis, which scripts/local-services.ps1
    then launches. The archive is already present in this checkout's .local
    directory, so this is only needed on a fresh clone.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$LocalDir = Join-Path $RepoRoot '.local'
$Url = 'https://github.com/tporadowski/redis/releases/download/v5.0.14.1/Redis-x64-5.0.14.1.zip'

New-Item -ItemType Directory -Force -Path $LocalDir | Out-Null
$zip = Join-Path $LocalDir (Split-Path $Url -Leaf)

if (-not (Test-Path $zip)) {
    Write-Host "Downloading Redis from $Url"
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $Url -OutFile $zip -UseBasicParsing
}

$target = Join-Path $LocalDir 'redis'
if (Test-Path $target) { Remove-Item -Recurse -Force $target }
Expand-Archive -Path $zip -DestinationPath $target -Force
Remove-Item $zip -Force

$exe = Join-Path $target 'redis-server.exe'
if (-not (Test-Path $exe)) { throw 'redis-server.exe not found after extraction' }
Write-Host "Redis extracted to $target" -ForegroundColor Green
