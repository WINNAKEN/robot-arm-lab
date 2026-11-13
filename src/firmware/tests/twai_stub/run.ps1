param([string]$Compiler = '')
$ErrorActionPreference = 'Stop'
$twaiProject = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../../..'))
$twaiBuild = Join-Path $twaiProject '.dev/esp32-can-evidence/build/twai_stub'
$twaiExecutable = Join-Path $twaiBuild 'test_twai_port.exe'
if ([string]::IsNullOrWhiteSpace($Compiler)) {
    $Compiler = Join-Path $twaiProject '.dev/tools/zig-x86_64-windows-0.17.0/zig.exe'
}
$twaiGlobalCache = Join-Path $twaiProject '.dev/tools/zig-cache-global'
$twaiLocalCache = Join-Path $twaiBuild 'zig-cache'
$twaiTemp = Join-Path $twaiBuild 'tmp'
foreach ($twaiPath in @($twaiBuild, $twaiGlobalCache, $twaiLocalCache, $twaiTemp)) {
    $twaiResolved = [IO.Path]::GetFullPath($twaiPath)
    if (-not $twaiResolved.StartsWith($twaiProject + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase)) {
        throw 'TWAI test output escapes the project'
    }
    New-Item -ItemType Directory -Path $twaiResolved -Force | Out-Null
}
$twaiEnvironment = @{}
foreach ($twaiName in @('ZIG_GLOBAL_CACHE_DIR', 'ZIG_LOCAL_CACHE_DIR', 'TEMP', 'TMP')) {
    $twaiEnvironment[$twaiName] = [Environment]::GetEnvironmentVariable($twaiName, 'Process')
}
$env:ZIG_GLOBAL_CACHE_DIR = $twaiGlobalCache
$env:ZIG_LOCAL_CACHE_DIR = $twaiLocalCache
$env:TEMP = $twaiTemp
$env:TMP = $twaiTemp
$twaiArguments = @(
    'c++', '-std=c++17', '-target', 'x86_64-windows-gnu', '-O0',
    '-Wall', '-Wextra', '-Werror', '-pedantic',
    '-I', (Join-Path $PSScriptRoot 'include'),
    '-I', $PSScriptRoot,
    '-I', (Join-Path $twaiProject 'src/firmware/components/robot_twai/include'),
    '-I', (Join-Path $twaiProject 'src/firmware/components/robot_can/include'),
    (Join-Path $PSScriptRoot 'stub_sdk.cpp'),
    (Join-Path $PSScriptRoot 'test_twai_port.cpp'),
    (Join-Path $twaiProject 'src/firmware/components/robot_twai/idf_twai_port.cpp'),
    '-o', $twaiExecutable
)
$twaiReport = [ordered]@{
    status = 'STARTED'
    scope = 'Production IdfTwaiPort compiled against host SDK stubs; no device access'
    compiler = $Compiler
    arguments = $twaiArguments
    device_access = 'NOT_RUN'
    target_build = 'SEPARATE_EVIDENCE_REQUIRED'
    compile_exit = $null
    run_exit = $null
}
Push-Location -LiteralPath $twaiProject
try {
    $twaiVersion = & $Compiler version 2>&1
    if ($LASTEXITCODE -ne 0) { throw 'Compiler version query failed' }
    $twaiReport.compiler_version = ($twaiVersion | Out-String).Trim()
    $twaiVersion | Set-Content -LiteralPath (Join-Path $twaiBuild 'compiler-version.txt') -Encoding utf8
    & $Compiler @twaiArguments *> (Join-Path $twaiBuild 'compile.txt')
    $twaiReport.compile_exit = $LASTEXITCODE
    if ($LASTEXITCODE -ne 0) { throw 'Compilation failed; inspect compile.txt' }
    $twaiOutput = & $twaiExecutable 2>&1
    $twaiReport.run_exit = $LASTEXITCODE
    $twaiOutput | Set-Content -LiteralPath (Join-Path $twaiBuild 'run.txt') -Encoding utf8
    $twaiReport.stdout = ($twaiOutput | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $twaiReport.stdout -notmatch '^TWAI_SDK_STUB_PASS cases=(\d+) assertions=(\d+)$') {
        throw 'SDK stub tests failed; inspect run.txt'
    }
    $twaiReport.cases = [int]$Matches[1]
    $twaiReport.assertions = [int]$Matches[2]
    $twaiReport.executable_sha256 = (Get-FileHash -LiteralPath $twaiExecutable -Algorithm SHA256).Hash.ToLowerInvariant()
    $twaiInputs = @(
        (Get-ChildItem -LiteralPath $PSScriptRoot -Recurse -File),
        (Get-ChildItem -LiteralPath (Join-Path $twaiProject 'src/firmware/components/robot_twai') -Recurse -File),
        (Get-Item -LiteralPath (Join-Path $twaiProject 'src/firmware/components/robot_can/include/robot_can/can_port.hpp'))
    ) | ForEach-Object { $_ } | Sort-Object FullName
    $twaiReport.source_sha256 = @($twaiInputs | ForEach-Object {
        [ordered]@{ path = $_.FullName; sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
    })
    $twaiReport.status = 'PASS'
} catch {
    $twaiReport.status = 'FAIL'
    $twaiReport.error = $_.Exception.Message
    throw
} finally {
    $twaiReport | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $twaiBuild 'result.json') -Encoding utf8
    foreach ($twaiName in $twaiEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($twaiName, $twaiEnvironment[$twaiName], 'Process')
    }
    Pop-Location
}
Write-Output $twaiReport.stdout
Write-Output (Join-Path $twaiBuild 'result.json')
