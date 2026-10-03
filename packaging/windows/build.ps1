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
    $defaultIscc = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"
    if (Test-Path $defaultIscc) {
        $iscc = @{ Source = $defaultIscc }
    } else {
        throw "Inno Setup 6 was not found. Install it, then run this script again."
    }
}

& $iscc.Source "packaging/windows/ROMIndexer.iss"