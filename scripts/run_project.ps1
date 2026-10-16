param(
    [ValidateSet('Setup','Api','Web','Test','Doctor')][string]$Mode = 'Api',
    [switch]$Demo,
    [switch]$WithTools,
    [string]$Python = 'python'
)
# Keep UTF-8 with BOM so Windows PowerShell 5.1 reads Chinese literals correctly.
$ErrorActionPreference = 'Stop'
$workspaceRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if ((Get-Location).Path.TrimEnd('\') -ne $workspaceRoot.TrimEnd('\')) {
    throw "请在项目根目录 $workspaceRoot 执行，脚本不会切换工作目录。"
}
$projectRoot = Join-Path $workspaceRoot 'demo\procurement'
$backendRoot = Join-Path $projectRoot 'backend'
$frontendRoot = Join-Path $projectRoot 'frontend'
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'

function Invoke-Checked {
    param([string]$Executable,[string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Executable 执行失败，退出码 $LASTEXITCODE" }
}

if ($Mode -eq 'Setup') {
    $setupArgs = @((Join-Path $workspaceRoot 'scripts\manage_project.py'),'setup')
    if ($WithTools) { $setupArgs += '--with-tools' }
    Invoke-Checked $Python $setupArgs
    exit 0
}
if ($Mode -ne 'Web' -and -not (Test-Path -LiteralPath $venvPython)) {
    throw '请先执行 .\scripts\run_project.ps1 -Mode Setup 安装项目运行环境。'
}
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = $backendRoot
switch ($Mode) {
    'Doctor' { Invoke-Checked $venvPython @((Join-Path $workspaceRoot 'scripts\doctor.py'),'--require-tools') }
    'Api' {
        if ($Demo) { $env:DEMO_SEED='true' }
        Invoke-Checked $venvPython @('-m','uvicorn','app.main:app','--app-dir',$backendRoot,'--host','127.0.0.1','--port','8000','--workers','1')
    }
    'Web' { Invoke-Checked 'npm' @('--prefix',$frontendRoot,'run','dev','--','--host','127.0.0.1') }
    'Test' {
        Invoke-Checked $venvPython @('-m','pytest',(Join-Path $backendRoot 'tests'),'-q','-c',(Join-Path $backendRoot 'pytest.ini'),'-p','no:cacheprovider',
            '--basetemp',(Join-Path $backendRoot '.test-work\tmp'))
        Invoke-Checked 'npm' @('--prefix',$frontendRoot,'run','build')
    }
}
