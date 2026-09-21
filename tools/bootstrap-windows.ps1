param(
    [Parameter(Mandatory=$true)][string]$Root,
    [Parameter(Mandatory=$true)][string]$Resources,
    [ValidateSet('auto', 'cpu', 'cuda', 'directml')][string]$Compute = 'auto'
)
$ErrorActionPreference = 'Stop'
$Root = [IO.Path]::GetFullPath($Root)
$Resources = [IO.Path]::GetFullPath($Resources)
New-Item -ItemType Directory -Force -Path "$Root/tools", "$Root/runtime", "$Root/src" | Out-Null
$uv = "$Root/tools/uv.exe"
if (!(Test-Path $uv)) {
    $archive = Join-Path ([IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString() + '.zip')
    $extract = $archive + '.unpacked'
    try {
        Invoke-WebRequest 'https://github.com/astral-sh/uv/releases/download/0.12.17/uv-x86_64-pc-windows-msvc.zip' -OutFile $archive
        Expand-Archive $archive -DestinationPath $extract
        $binary = Get-ChildItem $extract -Filter uv.exe -Recurse | Select-Object -First 1
        if (!$binary) { throw 'Private Python installer was not found in the archive.' }
        Copy-Item $binary.FullName $uv
    } finally {
        Remove-Item $archive, $extract -Force -Recurse -ErrorAction SilentlyContinue
    }
}
if ($Root -ne $Resources) {
    Copy-Item "$Resources/src/worker.py" "$Root/src/worker.py" -Force
    Copy-Item "$Resources/requirements-windows.txt" "$Root/requirements-windows.txt" -Force
    New-Item -ItemType Directory -Force -Path "$Root/upstream" | Out-Null
    Copy-Item "$Resources/upstream/*" "$Root/upstream" -Recurse -Force
}
$env:UV_PYTHON_INSTALL_DIR = "$Root/runtime/python"
$env:UV_CACHE_DIR = "$Root/runtime/cache"
function Invoke-Uv {
    & $uv @args
    if ($LASTEXITCODE -ne 0) { throw "Dependency setup failed (exit $LASTEXITCODE)." }
}
Push-Location $Root
try {
    # Pin the patch version and use its real directory. Minor-version junctions
    # can fail under Windows RedirectionGuard (ERROR_UNTRUSTED_MOUNT_POINT).
    # Keep this private runtime out of system Python registration as well.
    $pythonVersion = '3.12.14'
    Invoke-Uv python install --no-bin --no-registry $pythonVersion
    $basePython = "$Root/runtime/python/cpython-$pythonVersion-windows-x86_64-none/python.exe"
    if (!(Test-Path $basePython)) { throw 'The private Python runtime is missing.' }
    $python = "$Root/.venv/Scripts/python.exe"
    if (!(Test-Path $python)) { Invoke-Uv venv --python $basePython .venv }
    if ($Compute -eq 'auto') {
        # Presence is only an installation hint; the worker verifies actual CUDA usability.
        $nvidia = Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue
        if ($nvidia -or (Test-Path "$env:SystemRoot/System32/nvidia-smi.exe")) { $Compute = 'cuda' }
        else {
            $Compute = 'cpu'
            try {
                $amd = Get-CimInstance Win32_VideoController -ErrorAction Stop | Where-Object {
                    $_.PNPDeviceID -match 'VEN_1002' -or $_.Name -match 'AMD|Radeon'
                }
                if ($amd) { $Compute = 'directml' }
            } catch {
                Write-Warning 'Graphics detection failed. Installing CPU support; DirectML can be requested explicitly.'
            }
        }
    }
    Write-Output "Installing the $Compute engine. The app will report the processor it can actually use."
    if ($Compute -eq 'directml') {
        # Microsoft's published DirectML wheel requires this exact torch/vision pair.
        # Keep torchaudio on the matching version for upstream's optional beat helper.
        Invoke-Uv pip install --python $python --index-url https://download.pytorch.org/whl/cpu torch==2.4.1 torchaudio==2.4.1 torchvision==0.19.1
        @('torch==2.4.1', 'torchaudio==2.4.1', 'torchvision==0.19.1', 'torch-directml==0.2.5.dev240914') | Set-Content "$Root/runtime/torch-constraints.txt"
        Invoke-Uv pip install --python $python --constraint runtime/torch-constraints.txt torch-directml==0.2.5.dev240914
    } else {
        # Remove the old DirectML pins when explicitly switching back to CPU/CUDA.
        Invoke-Uv pip uninstall --python $python torch-directml torchvision
        $index = if ($Compute -eq 'cuda') { 'https://download.pytorch.org/whl/cu128' } else { 'https://download.pytorch.org/whl/cpu' }
        Invoke-Uv pip install --python $python --index-url $index torch==2.7.1 torchaudio==2.7.1
        @('torch==2.7.1', 'torchaudio==2.7.1') | Set-Content "$Root/runtime/torch-constraints.txt"
    }
    # Constraints prevent upstream dependency resolution from replacing the selected GPU build.
    Invoke-Uv pip install --python $python --constraint runtime/torch-constraints.txt -r requirements-windows.txt ./upstream
    Invoke-Uv pip check --python $python
    & $python -c "import torch, muscriptor, imageio_ffmpeg; print('CUDA available:', torch.cuda.is_available())"
    if ($LASTEXITCODE -ne 0) { throw 'The installed engine could not start.' }
    if ($Compute -eq 'directml') {
        & $python -c "import torch_directml; print('DirectML adapters:', torch_directml.device_count())"
        if ($LASTEXITCODE -ne 0) { throw 'DirectML could not start. Update the graphics driver and retry setup.' }
    }
    Invoke-Uv pip freeze --python $python | Set-Content "$Root/runtime/installed-packages.txt"
    Write-Output 'Local environment is ready.'
} finally {
    Pop-Location
}
