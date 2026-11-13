param([switch]$Mutations)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
$firmware = Join-Path $projectRoot 'src/firmware'
$build = Join-Path $projectRoot '.dev/esp32-can-evidence/host-build'
$zig = Join-Path $projectRoot '.dev/tools/zig-x86_64-windows-0.17.0/zig.exe'
New-Item -ItemType Directory -Force -Path $build | Out-Null
$env:ZIG_GLOBAL_CACHE_DIR = Join-Path $projectRoot '.dev/tools/zig-cache-global'
$env:ZIG_LOCAL_CACHE_DIR = Join-Path $build 'zig-cache-local'
$env:TEMP = Join-Path $build 'tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
$core = Join-Path $firmware 'components/robot_core'
$can = Join-Path $firmware 'components/robot_can'
$results = @()
function Invoke-LinkTest([string]$Name, [string]$Source, [bool]$ExpectPass) {
 $exe = Join-Path $build "$Name.exe"
 & $zig c++ -std=c++17 -target x86_64-windows-gnu -O0 -g -Wall -Wextra -Werror -pedantic `
    -I (Join-Path $core 'include') -I (Join-Path $can 'include') `
    -I (Join-Path $firmware 'tests/host') `
    (Join-Path $core 'mks_codec.cpp') (Join-Path $core 'stop_coordinator.cpp') `
    $Source (Join-Path $PSScriptRoot 'test_stop_link.cpp') `
    -o $exe 2>&1 | Out-File (Join-Path $build "$Name-compile-output.txt") -Encoding utf8
 if ($LASTEXITCODE -ne 0) { Get-Content (Join-Path $build "$Name-compile-output.txt"); throw "$Name compile failed" }
 & $exe 2>&1 | Out-File (Join-Path $build "$Name-run-output.txt") -Encoding utf8
 $runExit = $LASTEXITCODE
 Get-Content (Join-Path $build "$Name-run-output.txt") -Tail 3 | Write-Host
 if (($ExpectPass -and $runExit -ne 0) -or (!$ExpectPass -and $runExit -eq 0)) { throw "$Name unexpected exit $runExit" }
 if (!$ExpectPass -and ($runExit -ne 1 -or !(Select-String -LiteralPath (Join-Path $build "$Name-run-output.txt") -SimpleMatch 'CHECK FAILED:'))) {
     throw "$Name did not fail through the test assertion oracle"
 }
 return [pscustomobject]@{name=$Name; compile_exit=0; run_exit=$runExit; expected_pass=$ExpectPass;
     matched_expectation=$true; exe_sha256=(Get-FileHash $exe -Algorithm SHA256).Hash}
}
$sourcePath = Join-Path $can 'stop_link.cpp'
$results += Invoke-LinkTest 'stop-link' $sourcePath $true
if ($Mutations) {
 $source = Get-Content $sourcePath -Raw
 $mutants = @(
     @{Name='ignore-final-health'; From=' || !closed_result_.healthy'; To=''},
     @{Name='allow-10ms-gap'; From='if (now - last_poll_ >= 10)'; To='if (now - last_poll_ > 10)'}
 )
 foreach ($m in $mutants) {
     if (($source.Split(@($m.From), [StringSplitOptions]::None).Count - 1) -ne 1) { throw "Mutation anchor not unique: $($m.Name)" }
     $mutated = Join-Path $build "$($m.Name).cpp"
     [IO.File]::WriteAllText($mutated, $source.Replace($m.From,$m.To))
     $results += Invoke-LinkTest $m.Name $mutated $false
 }
}
[pscustomobject]@{status='HOST_LINK_PASS'; executed_at=(Get-Date -Format o);
    hardware_accessed=$false; results=$results} |
    ConvertTo-Json -Depth 5 | Set-Content (Join-Path $build 'result.json') -Encoding utf8
