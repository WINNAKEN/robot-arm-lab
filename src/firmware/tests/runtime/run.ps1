param([switch]$Mutations)
$ErrorActionPreference='Stop'
$projectRoot=(Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
$components=Join-Path $projectRoot 'src/firmware/components'
$build=Join-Path $projectRoot '.dev/runtime-refresh-evidence/build'
$zig=Join-Path $projectRoot '.dev/tools/zig-x86_64-windows-0.17.0/zig.exe'
New-Item -ItemType Directory -Force $build | Out-Null
$env:ZIG_GLOBAL_CACHE_DIR=Join-Path $projectRoot '.dev/tools/zig-cache-global'
$env:ZIG_LOCAL_CACHE_DIR=Join-Path $build 'zig-cache-local'
$env:TEMP=Join-Path $build 'tmp'; $env:TMP=$env:TEMP
New-Item -ItemType Directory -Force $env:TEMP | Out-Null
function Run-Test([string]$Name,[string]$Source,[bool]$Expected,[string]$RunSource=""){
 if($RunSource -eq ""){$RunSource=Join-Path $components 'robot_run/bench_run.cpp'}
 $exe=Join-Path $build "$Name.exe"
 $arguments=@('c++','-std=c++17','-target','x86_64-windows-gnu','-O0','-g','-Wall','-Wextra','-Werror','-pedantic')
 foreach($component in @('robot_config','robot_boot','robot_run','robot_gate','robot_can','robot_core')){$arguments+=@('-I',(Join-Path $components "$component/include"))}
 $arguments+=@($Source,(Join-Path $components 'robot_gate/control_gate.cpp'),(Join-Path $components 'robot_can/stop_link.cpp'),(Join-Path $components 'robot_core/stop_coordinator.cpp'),(Join-Path $components 'robot_core/mks_codec.cpp'),(Join-Path $components 'robot_boot/config_codec.cpp'),(Join-Path $components 'robot_config/codec.cpp'),$RunSource,(Join-Path $PSScriptRoot 'test_runtime.cpp'),'-o',$exe)
 & $zig @arguments 2>&1 | Out-File (Join-Path $build "$Name-compile.log") -Encoding utf8
 if($LASTEXITCODE -ne 0){throw "$Name compile failed"}
 & $exe 2>&1 | Out-File (Join-Path $build "$Name-run.log") -Encoding utf8
 $code=$LASTEXITCODE
 if(($Expected -and $code -ne 0) -or (!$Expected -and $code -eq 0)){throw "$Name unexpected result $code"}
 Get-Content (Join-Path $build "$Name-run.log") | Write-Host
 [pscustomobject]@{name=$Name;exit=$code;expected_pass=$Expected;sha256=(Get-FileHash $exe -Algorithm SHA256).Hash}
}
$source=Join-Path $components 'robot_boot/supervisor.cpp'
$results=@(Run-Test 'runtime' $source $true)
if($Mutations){
 $runPath=Join-Path $components 'robot_run/bench_run.cpp';$raw=Get-Content $runPath -Raw
 $mutants=@(
  @{Name='keepalive-renews-settings';From='const auto result=gate_.handle(port_.now_ms(),snapshot_,r);';To='const auto result=gate_.handle(port_.now_ms(),snapshot_,r);if(r.op==robot_gate::Op::Renew)for(auto& axis:configurations_)for(auto& sample:axis){sample.dequeued_at=port_.now_ms();}'},
  @{Name='wrong-axis-config-admitted';From='f.id==profile_.gate.axes[read_.axis]';To='f.id>=1'},
  @{Name='urgent-config-starves-diagnostics';From='if(!diagnostic_priority && (config_urgent || ordinary_config))';To='if((!diagnostic_priority || config_urgent) && (config_urgent || ordinary_config))'},
  @{Name='config-completes-position-proof';From='if(config_refreshes_<max_time)++config_refreshes_;';To='if(config_refreshes_<max_time)++config_refreshes_;if(completed_)status_.state=State::Ready;'},
  @{Name='wrong-value-config-admitted';From='if(parsed_config.value!=expected_configuration(read_.axis,read_.code))';To='if(parsed_config.value==4294967295u)'}
 )
 foreach($m in $mutants){if($raw.Split(@($m.From),[StringSplitOptions]::None).Count-1 -ne 1){throw "Mutation anchor mismatch $($m.Name)"};$path=Join-Path $build "$($m.Name).cpp";[IO.File]::WriteAllText($path,$raw.Replace($m.From,$m.To));$results+=Run-Test $m.Name $source $false $path}
}
[pscustomobject]@{status='OFFLINE_RUNTIME_HOST_PASS';hardware='NOT_RUN';sdk_build='NOT_RUN';results=$results} | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $build 'result.json') -Encoding utf8
