$ErrorActionPreference = "Stop"

pyinstaller --noconfirm --clean --windowed --onedir --name ROMIndexer `
    --add-data "app/templates;app/templates" `
    --collect-all fastapi `
    --collect-all starlette `
    --collect-all jinja2 `
    --collect-all multipart `
    --collect-all uvicorn `
    --collect-all pystray `
    --collect-all PIL `
    launcher.py

$iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if (-not $iscc) {
    $candidatePaths = @(
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
    )

    $resolvedIscc = $candidatePaths | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
    if ($resolvedIscc) {
        $iscc = @{ Source = $resolvedIscc }
    } else {
        throw "Inno Setup 6 was not found. Install it, then run this script again."
    }
}

& $iscc.Source "packaging/windows/ROMIndexer.iss"