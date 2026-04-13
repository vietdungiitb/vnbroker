param(
    [string]$EnvFile = ".env.dnse",
    [string]$PythonExe = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Test-Path -Path $EnvFile)) {
    Write-Host "Env file not found: $EnvFile" -ForegroundColor Red
    Write-Host "Create it from .env.dnse.example and fill real credentials." -ForegroundColor Yellow
    exit 2
}

$lines = Get-Content -Path $EnvFile
foreach ($line in $lines) {
    $trimmed = $line.Trim()
    if ([string]::IsNullOrWhiteSpace($trimmed)) { continue }
    if ($trimmed.StartsWith("#")) { continue }

    $parts = $trimmed.Split("=", 2)
    if ($parts.Length -ne 2) { continue }

    $name = $parts[0].Trim()
    $value = $parts[1].Trim()

    if ([string]::IsNullOrWhiteSpace($name)) { continue }
    [Environment]::SetEnvironmentVariable($name, $value, "Process")
}

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    if (Test-Path -Path ".venv\Scripts\python.exe") {
        $PythonExe = ".venv\Scripts\python.exe"
    }
    else {
        $PythonExe = "python"
    }
}

Write-Host "Running DNSE quickcheck with env file: $EnvFile" -ForegroundColor Cyan
& $PythonExe -m tests.examples.dnse_qa_quickcheck
$code = $LASTEXITCODE
if ($code -ne 0) {
    Write-Host "DNSE quickcheck failed with exit code: $code" -ForegroundColor Red
    exit $code
}

Write-Host "DNSE quickcheck passed" -ForegroundColor Green
exit 0
