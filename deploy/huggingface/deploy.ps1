# Stage the backend files and push them to a Hugging Face Space.
# Usage (PowerShell, from anywhere):
#   $env:HF_TOKEN = "hf_xxx"          # a WRITE token; never commit it
#   .\deploy\huggingface\deploy.ps1 -SpaceId "your-username/your-space-name"
# Nothing in the project is modified; a temp folder is created and deleted.
param(
    [Parameter(Mandatory = $true)][string]$SpaceId
)

$ErrorActionPreference = 'Stop'

if (-not $env:HF_TOKEN) { throw 'Set $env:HF_TOKEN to a Hugging Face WRITE token first.' }
if ($SpaceId -notmatch '^[\w.-]+/[\w.-]+$') { throw 'SpaceId must look like "username/space-name".' }

$root  = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$stage = Join-Path $env:TEMP 'hf-space-stage'

foreach ($p in 'backend\src', 'backend\kb_index', 'backend\pyproject.toml', 'backend\poetry.lock') {
    if (-not (Test-Path (Join-Path $root $p))) { throw "Missing $p - run from the project checkout." }
}

if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Path $stage | Out-Null

# robocopy exit codes 0-7 mean success
robocopy (Join-Path $root 'backend\src') (Join-Path $stage 'src') /E /XD __pycache__ /XF *.pyc /NFL /NDL /NJH /NJS | Out-Null
robocopy (Join-Path $root 'backend\kb_index') (Join-Path $stage 'kb_index') /E /NFL /NDL /NJH /NJS | Out-Null
Copy-Item (Join-Path $root 'backend\pyproject.toml'), (Join-Path $root 'backend\poetry.lock') $stage
Copy-Item (Join-Path $PSScriptRoot 'Dockerfile'), (Join-Path $PSScriptRoot 'README.md') $stage

Push-Location $stage
try {
    git init -q -b main
    git add -A
    git -c user.name='deploy' -c user.email='deploy@localhost' commit -q -m "Deploy $(Get-Date -Format s)"

    $user  = $SpaceId.Split('/')[0]
    $basic = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${user}:$($env:HF_TOKEN)"))
    git -c "http.extraHeader=Authorization: Basic $basic" push --force "https://huggingface.co/spaces/$SpaceId" main:main
    if ($LASTEXITCODE -ne 0) { throw "git push failed (exit $LASTEXITCODE)." }
    Write-Host "Pushed. Watch the build at https://huggingface.co/spaces/$SpaceId"
}
finally {
    Pop-Location
    Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
}
