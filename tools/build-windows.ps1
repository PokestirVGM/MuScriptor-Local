$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (!(Test-Path 'upstream/muscriptor/transcription_model.py')) {
    git clone https://github.com/muscriptor/muscriptor.git upstream
    if ($LASTEXITCODE -ne 0) { throw 'Could not fetch official MuScriptor source.' }
}
$revision = (Get-Content upstream-revision.txt -Raw).Trim()
git -C upstream checkout $revision
if ($LASTEXITCODE -ne 0) { throw 'Could not select the pinned official source revision.' }
python -m pip install -r requirements-windows-ui.txt
if ($LASTEXITCODE -ne 0) { throw 'Could not install build dependencies.' }
python -m PyInstaller --noconfirm --clean --windowed --onedir --name 'MuScriptor Local' --distpath build/windows/dist --workpath build/windows/work --specpath build/windows `
    --add-data 'src/worker.py;resources/src' `
    --add-data 'tools/bootstrap-windows.ps1;resources/tools' `
    --add-data 'requirements-windows.txt;resources' `
    --add-data 'upstream/muscriptor;resources/upstream/muscriptor' `
    --add-data 'upstream/pyproject.toml;resources/upstream' `
    --add-data 'upstream/README.md;resources/upstream' `
    --add-data 'upstream/LICENSE;resources/upstream' src/WindowsApp.py
if ($LASTEXITCODE -ne 0) { throw 'Windows build failed.' }
Copy-Item WINDOWS.md 'build/windows/dist/MuScriptor Local/Read Me First.md' -Force
New-Item -ItemType Directory -Force -Path dist/windows | Out-Null
Compress-Archive -Path 'build/windows/dist/MuScriptor Local' -DestinationPath 'dist/windows/MuScriptor Local - Windows x64 Preview.zip' -Force
Write-Output 'Built dist/windows/MuScriptor Local - Windows x64 Preview.zip'
