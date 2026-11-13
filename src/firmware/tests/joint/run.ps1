param([switch]$Mutations,[switch]$Regressions)
$ErrorActionPreference='Stop'
$projectRoot=(Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
$components=Join-Path $projectRoot 'src/firmware/components'
$build=Join-Path $projectRoot '.dev/joint-control-evidence/build'
$zig=Join-Path $projectRoot '.dev/tools/zig-x86_64-windows-0.17.0/zig.exe'
New-Item -ItemType Directory -Force $build | Out-Null
$env:ZIG_GLOBAL_CACHE_DIR=Join-Path $projectRoot '.dev/tools/zig-cache-global'
$env:ZIG_LOCAL_CACHE_DIR=Join-Path $build 'zig-cache-local'
$env:TEMP=Join-Path $build 'tmp';$env:TMP=$env:TEMP
New-Item -ItemType Directory -Force $env:TEMP | Out-Null
& py -B (Join-Path $PSScriptRoot 'oracle.py') --out (Join-Path $build 'oracle.hpp')
if($LASTEXITCODE -ne 0){throw 'oracle failed'}
function Run-Joint([string]$Name,[string]$Test,[string]$Override,[bool]$Expected){
 $argsList=@('c++','-std=c++17','-target','x86_64-windows-gnu','-O0','-g','-Wall','-Wextra','-Werror','-pedantic','-I',$build)
 if($Override){$argsList+=@('-I',$Override)}
 foreach($component in @('robot_phone','robot_boot','robot_run','robot_gate','robot_config','robot_can','robot_core')){$argsList+=@('-I',(Join-Path $components "$component/include"))}
 foreach($file in @('robot_phone/wire.cpp','robot_phone/owner.cpp','robot_boot/supervisor.cpp','robot_boot/config_codec.cpp','robot_run/bench_run.cpp','robot_gate/control_gate.cpp','robot_config/codec.cpp','robot_can/stop_link.cpp','robot_core/stop_coordinator.cpp','robot_core/mks_codec.cpp')){$argsList+=Join-Path $components $file}
 $exe=Join-Path $build "$Name.exe";$argsList+=@($Test,'-o',$exe)
 $argsList|ConvertTo-Json|Set-Content (Join-Path $build "$Name-command.json") -Encoding utf8
 & $zig @argsList 2>&1|Out-File (Join-Path $build "$Name-compile.txt") -Encoding utf8
 if($LASTEXITCODE -ne 0){throw "$Name compile failed"}
 & $exe 2>&1|Out-File (Join-Path $build "$Name-test.txt") -Encoding utf8
 $code=$LASTEXITCODE;$log=Get-Content (Join-Path $build "$Name-test.txt") -Raw
 if(($Expected -and $code -ne 0) -or (!$Expected -and ($code -ne 1 -or $log -notmatch 'FAIL'))){throw "$Name wrong test result $code"}
 Get-Content (Join-Path $build "$Name-test.txt")|Select-Object -Last 3|Write-Host
 [pscustomobject]@{name=$Name;compile_exit=0;test_exit=$code;expected_positive=$Expected;exe_sha256=(Get-FileHash $exe).Hash}
}
$test=Join-Path $PSScriptRoot 'test_joint.cpp'
$results=@(Run-Joint 'joint' $test '' $true)
if($Mutations){
 $source=Get-Content (Join-Path $components 'robot_run/include/robot_run/joint_angles.hpp') -Raw
 foreach($m in @(
  @{Name='degrees-as-radians';From='case StepUnit::CadDegrees: delta=input.value*(pi/180.);break;';To='case StepUnit::CadDegrees: delta=input.value;break;'},
  @{Name='offset-omitted';From='geometric=delta+offset';To='geometric=delta'},
  @{Name='unmeasured-allowed';From='if(!cal.measured ||';To='if(false ||'}
 )){
  if($source.Split(@($m.From),[StringSplitOptions]::None).Count-1 -ne 1){throw 'mutation anchor'}
  $override=Join-Path $build "$($m.Name)/include"
  New-Item -ItemType Directory -Force (Join-Path $override 'robot_run')|Out-Null
  [IO.File]::WriteAllText((Join-Path $override 'robot_run/joint_angles.hpp'),$source.Replace($m.From,$m.To))
  $results+=Run-Joint $m.Name $test $override $false
 }
}
if($Regressions){foreach($case in @(@('boot','boot/test_boot.cpp'),@('runtime','runtime/test_runtime.cpp'),@('phone','phone/test_phone.cpp'))){$results+=Run-Joint $case[0] (Join-Path (Split-Path $PSScriptRoot) $case[1]) '' $true}}
$results|ConvertTo-Json -Depth 4|Set-Content (Join-Path $build 'results.json') -Encoding utf8
