param([switch]$Mutations)
$ErrorActionPreference='Stop'
$projectRoot=(Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
$components=Join-Path $projectRoot 'src/firmware/components'
$build=Join-Path $projectRoot '.dev/normal-can-evidence/build'
$zig=Join-Path $projectRoot '.dev/tools/zig-x86_64-windows-0.17.0/zig.exe'
New-Item -ItemType Directory -Force $build | Out-Null
$env:ZIG_GLOBAL_CACHE_DIR=Join-Path $projectRoot '.dev/tools/zig-cache-global'
$env:ZIG_LOCAL_CACHE_DIR=Join-Path $build 'zig-cache-local'
$env:TEMP=Join-Path $build 'tmp'; $env:TMP=$env:TEMP
New-Item -ItemType Directory -Force $env:TEMP | Out-Null
function Run-Test([string]$Name,[string]$Source,[bool]$Expected){
 $exe=Join-Path $build "$Name.exe"
 $arguments=@('c++','-std=c++17','-target','x86_64-windows-gnu','-O0','-g','-Wall','-Wextra','-Werror','-pedantic')
 foreach($component in @('robot_config','robot_run','robot_gate','robot_can','robot_core')){$arguments+=@('-I',(Join-Path $components "$component/include"))}
 $arguments+=@($Source,(Join-Path $components 'robot_gate/control_gate.cpp'),(Join-Path $components 'robot_can/stop_link.cpp'),(Join-Path $components 'robot_core/stop_coordinator.cpp'),(Join-Path $components 'robot_core/mks_codec.cpp'),(Join-Path $components 'robot_config/codec.cpp'),(Join-Path $PSScriptRoot 'test_run.cpp'),'-o',$exe)
 & $zig @arguments 2>&1 | Out-File (Join-Path $build "$Name-compile.log") -Encoding utf8
 if($LASTEXITCODE -ne 0){throw "$Name compile failed"}
 & $exe 2>&1 | Out-File (Join-Path $build "$Name-run.log") -Encoding utf8
 $code=$LASTEXITCODE
 if(($Expected -and $code -ne 0) -or (!$Expected -and $code -eq 0)){throw "$Name unexpected result $code"}
 Get-Content (Join-Path $build "$Name-run.log") | Write-Host
 [pscustomobject]@{name=$Name;exit=$code;expected_pass=$Expected;sha256=(Get-FileHash $exe -Algorithm SHA256).Hash}
}
$source=Join-Path $components 'robot_run/bench_run.cpp'
$results=@(Run-Test 'run' $source $true)
if($Mutations){
 $raw=Get-Content $source -Raw
 foreach($m in @(@{Name='accept-is-success';From='const auto terminal=alerts&(TxSuccess|TxFailed);';To='const auto terminal=(alerts&(TxSuccess|TxFailed)) | (inflight_?TxSuccess:0u);'},@{Name='normal-during-stop';From='if(status_.state==State::Stopping){stop_poll(false);return;}';To='if(status_.state==State::Stopping){stop_poll(false); port_.submit(robot_can::WireFrame{1,2,{0x31,0x32}},port_.now_ms()+50);return;}'})){
  if($raw.Split(@($m.From),[StringSplitOptions]::None).Count-1 -ne 1){throw 'Mutation anchor mismatch'}
  $path=Join-Path $build "$($m.Name).cpp";[IO.File]::WriteAllText($path,$raw.Replace($m.From,$m.To))
  $results+=Run-Test $m.Name $path $false
 }
}
[pscustomobject]@{status='OFFLINE_RUN_HOST_PASS';hardware='NOT_RUN';sdk_build='NOT_RUN';results=$results} | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $build 'result.json') -Encoding utf8
