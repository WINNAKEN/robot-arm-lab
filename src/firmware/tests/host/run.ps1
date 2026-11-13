param([switch]$Mutations)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
$core = Join-Path $projectRoot 'src/firmware/components/robot_core'
$build = Join-Path $projectRoot '.dev/firmware-core-evidence/build'
$zig = Join-Path $projectRoot '.dev/tools/zig-x86_64-windows-0.17.0/zig.exe'
New-Item -ItemType Directory -Force -Path $build | Out-Null
$env:ZIG_GLOBAL_CACHE_DIR = Join-Path $projectRoot '.dev/tools/zig-cache-global'
$env:ZIG_LOCAL_CACHE_DIR = Join-Path $build 'zig-cache-local'
$env:TEMP = Join-Path $build 'tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
$results = @()
function Invoke-CoreTest([string]$Name, [string]$StopSource, [bool]$ExpectPass) {
    $exe = Join-Path $build "$Name.exe"
    $compileLog = Join-Path $build "$Name-compile.log"
    $runLog = Join-Path $build "$Name-run.log"
    & $zig c++ -std=c++17 -target x86_64-windows-gnu -O0 -g -Wall -Wextra -Werror -pedantic `
        -I (Join-Path $core 'include') -I $PSScriptRoot `
        (Join-Path $core 'mks_codec.cpp') $StopSource `
        (Join-Path $PSScriptRoot 'main.cpp') (Join-Path $PSScriptRoot 'test_codec.cpp') `
        (Join-Path $PSScriptRoot 'test_stop.cpp') -o $exe 2>&1 | Out-File $compileLog -Encoding utf8
    if ($LASTEXITCODE -ne 0) { Get-Content $compileLog; throw "$Name compile failed" }
    & $exe 2>&1 | Out-File $runLog -Encoding utf8
    $runExit = $LASTEXITCODE
    if (($ExpectPass -and $runExit -ne 0) -or (!$ExpectPass -and $runExit -eq 0)) {
        Get-Content $runLog; throw "$Name unexpected exit $runExit"
    }
    Get-Content $runLog -Tail 3 | Write-Host
    return [pscustomobject]@{name=$Name; compile_exit=0; run_exit=$runExit;
        expected_pass=$ExpectPass; matched_expectation=$true;
        executable_sha256=(Get-FileHash $exe -Algorithm SHA256).Hash}
}
$stopSource = Join-Path $core 'stop_coordinator.cpp'
$results += Invoke-CoreTest 'host-core' $stopSource $true
if ($Mutations) {
    $source = Get-Content $stopSource -Raw
    $mutationsToRun = @(
        @{Name='old-1600ms'; From='overall_deadline_ = now + 3600;'; To='overall_deadline_ = now + 1600;'},
        @{Name='old-100ms-requery'; From='static_cast<std::uint64_t>(next_slot_) * 60;'; To='static_cast<std::uint64_t>(next_slot_) * 25;'}
    )
    foreach ($m in $mutationsToRun) {
        if (($source.Split(@($m.From), [StringSplitOptions]::None).Count - 1) -ne 1) {
            throw "Mutation anchor must match exactly once: $($m.Name)"
        }
        $mutant = Join-Path $build "$($m.Name).cpp"
        [IO.File]::WriteAllText($mutant, $source.Replace($m.From, $m.To))
        $results += Invoke-CoreTest $m.Name $mutant $false
    }
}
$sources = Get-ChildItem (Join-Path $projectRoot 'src/firmware') -File -Recurse |
    Where-Object { $_.Extension -in '.cpp','.hpp','.txt','.ps1' } |
    ForEach-Object { [pscustomobject]@{path=$_.FullName.Substring($projectRoot.Length + 1);
        sha256=(Get-FileHash $_.FullName -Algorithm SHA256).Hash} }
[pscustomobject]@{status='HOST_CORE_PASS'; executed_at=(Get-Date -Format o);
    compiler='Zig 0.17.0 / Clang 22.1.8'; target='x86_64-windows-gnu';
    hardware_run=$false; esp_idf_build='NOT_RUN'; results=$results; sources=$sources} |
    ConvertTo-Json -Depth 6 | Set-Content (Join-Path $build 'result.json') -Encoding utf8
Write-Host 'HOST_CORE_EVIDENCE_SAVED'
