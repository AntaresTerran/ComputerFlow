param([switch]$Setup, [switch]$Doctor, [switch]$StopServer, [switch]$Microphone,
    [ValidateSet('enroll', 'status', 'delete')][string]$Speaker)
$ErrorActionPreference = 'Stop'
$taskEnvironment = @{
    COMPUTERFLOW_HOME = $PSScriptRoot
    UV_CACHE_DIR = Join-Path $PSScriptRoot '.computerflow/cache'
    UV_PROJECT_ENVIRONMENT = Join-Path $PSScriptRoot '.computerflow/venv'
    UV_PYTHON_INSTALL_DIR = Join-Path $PSScriptRoot '.computerflow/python'
    UV_PYTHON_BIN_DIR = Join-Path $PSScriptRoot '.computerflow/bin'
    TEMP = Join-Path $PSScriptRoot '.computerflow/temp'
    TMP = Join-Path $PSScriptRoot '.computerflow/temp'
}
$taskPreviousEnvironment = @{}
Push-Location $PSScriptRoot
try {
    foreach ($taskVariable in $taskEnvironment.Keys) {
        $taskPreviousEnvironment[$taskVariable] = [Environment]::GetEnvironmentVariable($taskVariable)
        [Environment]::SetEnvironmentVariable($taskVariable, $taskEnvironment[$taskVariable])
    }
    [System.IO.Directory]::CreateDirectory($env:TEMP) | Out-Null
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw 'uv fehlt. Installation: https://docs.astral.sh/uv/getting-started/installation/'
    }
    & uv sync --locked --extra desktop --link-mode copy
    if ($LASTEXITCODE -ne 0) {
        # A cloud-synced workspace can briefly lock package metadata during replacement.
        # One bounded retry lets uv repair an interrupted environment without deleting it.
        Write-Output 'Lokale Paket-Synchronisierung unterbrochen; ein Reparaturversuch folgt.'
        & uv sync --locked --extra desktop --link-mode copy
    }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $taskConfig = Join-Path $PSScriptRoot 'config.yaml'
    if ($Microphone) {
        & uv run --no-sync computerflow --config $taskConfig microphone
        exit $LASTEXITCODE
    }
    if ($Speaker) {
        & uv run --no-sync computerflow --config $taskConfig speaker $Speaker
        exit $LASTEXITCODE
    }
    if ($Setup -or -not (Test-Path -LiteralPath $taskConfig)) {
        & uv run --no-sync computerflow --config $taskConfig setup
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        if ($Setup) { exit 0 }
    }
    if ($StopServer) {
        & uv run --no-sync computerflow --config $taskConfig server stop
    } elseif ($Doctor) {
        & uv run --no-sync computerflow --config $taskConfig server start
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        & uv run --no-sync computerflow --config $taskConfig doctor
    } else {
        & uv run --no-sync computerflow --config $taskConfig audio-setup
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        & uv run --no-sync computerflow --config $taskConfig listen
    }
    exit $LASTEXITCODE
} finally {
    foreach ($taskVariable in $taskPreviousEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($taskVariable, $taskPreviousEnvironment[$taskVariable])
    }
    Pop-Location
}
