param([switch]$Mutations)
$ErrorActionPreference='Stop'
$projectRoot=(Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
$core=Join-Path $projectRoot 'src/firmware/components/robot_gate'
$build=Join-Path $projectRoot '.dev/control-gate-evidence/build'
$zig=Join-Path $projectRoot '.dev/tools/zig-x86_64-windows-0.17.0/zig.exe'
New-Item -ItemType Directory -Force $build | Out-Null
$env:ZIG_GLOBAL_CACHE_DIR=Join-Path $projectRoot '.dev/tools/zig-cache-global'
$env:ZIG_LOCAL_CACHE_DIR=Join-Path $build 'zig-cache-local'
$env:TEMP=Join-Path $build 'tmp'; $env:TMP=$env:TEMP
New-Item -ItemType Directory -Force $env:TEMP | Out-Null
function Run-Test([string]$Name,[string]$Source,[bool]$Expected) {
 $exe=Join-Path $build "$Name.exe"
 & $zig c++ -std=c++17 -target x86_64-windows-gnu -O0 -g -Wall -Wextra -Werror -pedantic -I (Join-Path $core 'include') $Source (Join-Path $PSScriptRoot 'test_gate.cpp') -o $exe 2>&1 | Out-File (Join-Path $build "$Name-compile.log") -Encoding utf8
 if($LASTEXITCODE -ne 0){throw "$Name compile failed"}
 & $exe 2>&1 | Out-File (Join-Path $build "$Name-run.log") -Encoding utf8
 $code=$LASTEXITCODE
 if(($Expected -and $code -ne 0) -or (!$Expected -and $code -eq 0)){throw "$Name unexpected result $code"}
 Get-Content (Join-Path $build "$Name-run.log") | Write-Host
 [pscustomobject]@{name=$Name;exit=$code;expected_pass=$Expected;sha256=(Get-FileHash $exe -Algorithm SHA256).Hash}
}
$source=Join-Path $core 'control_gate.cpp'
$results=@(Run-Test 'gate' $source $true)
if($Mutations){
 $raw=Get-Content $source -Raw
 foreach($m in @(@{Name='consume-expiry-removed';From='now>=intent_.dispatch_before';To='false'},@{Name='lease-boundary-late';From='now>=lease_until_';To='now>lease_until_'})){
  $count=$raw.Split(@($m.From),[StringSplitOptions]::None).Count-1
  if($count -ne 2){throw "Unexpected mutation anchor count $count"}
  $path=Join-Path $build "$($m.Name).cpp"
  [IO.File]::WriteAllText($path,$raw.Replace($m.From,$m.To))
  $results+=Run-Test $m.Name $path $false
 }
}
$files=@(Get-ChildItem $core,$PSScriptRoot -Recurse -File | ForEach-Object {[pscustomobject]@{path=$_.FullName.Substring($projectRoot.Length+1);sha256=(Get-FileHash $_.FullName -Algorithm SHA256).Hash}})
[pscustomobject]@{status='OFFLINE_GATE_HOST_PASS';hardware='NOT_RUN';sdk_build='NOT_RUN';results=$results;sources=$files} | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $build 'result.json') -Encoding utf8
