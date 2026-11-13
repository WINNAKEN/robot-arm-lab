param([switch]$Mutations)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
$components=Join-Path $root 'src/firmware/components'
$build=Join-Path $root '.dev/phone-angle-evidence/build'
$zig=Join-Path $root '.dev/tools/zig-x86_64-windows-0.17.0/zig.exe'
New-Item -ItemType Directory -Force $build|Out-Null
$env:ZIG_GLOBAL_CACHE_DIR=Join-Path $root '.dev/tools/zig-cache-global';$env:ZIG_LOCAL_CACHE_DIR=Join-Path $build 'cache'
$env:TEMP=Join-Path $build 'tmp';$env:TMP=$env:TEMP;New-Item -ItemType Directory -Force $env:TEMP|Out-Null
function Compile-Run([string]$name,[string]$owner,[string]$wire,[bool]$positive){
 $exe=Join-Path $build "$name.exe";$a=@('c++','-std=c++17','-target','x86_64-windows-gnu','-O0','-g','-Wall','-Wextra','-Werror','-pedantic')
 foreach($c in @('robot_phone','robot_boot','robot_run','robot_gate','robot_config','robot_can','robot_core')){$a+=@('-I',(Join-Path $components "$c/include"))}
 foreach($f in @('robot_boot/supervisor.cpp','robot_boot/config_codec.cpp','robot_run/bench_run.cpp','robot_gate/control_gate.cpp','robot_config/codec.cpp','robot_can/stop_link.cpp','robot_core/stop_coordinator.cpp','robot_core/mks_codec.cpp')){$a+=Join-Path $components $f}
 $a+=@($owner,$wire,(Join-Path $PSScriptRoot 'test_angle.cpp'),'-o',$exe);$a|ConvertTo-Json|Set-Content (Join-Path $build "$name-command.json") -Encoding utf8
 & $zig @a *> (Join-Path $build "$name-compile.txt");if($LASTEXITCODE -ne 0){throw "$name compile"}
 & $exe *> (Join-Path $build "$name-test.txt");$exit=$LASTEXITCODE;$text=Get-Content (Join-Path $build "$name-test.txt") -Raw
 if(($positive -and $exit -ne 0)-or(!$positive -and ($exit -ne 1-or$text -notmatch 'FAIL'))){throw "$name test exit $exit"}
 Get-Content (Join-Path $build "$name-test.txt")|Select-Object -Last 1|Write-Host
 [pscustomobject]@{name=$name;compile=0;exit=$exit;positive=$positive;exe_hash=(Get-FileHash $exe).Hash}
}
$owner=Join-Path $components 'robot_phone/owner.cpp';$wire=Join-Path $components 'robot_phone/wire.cpp'
$results=@(Compile-Run 'angle' $owner $wire $true)
& node (Join-Path $PSScriptRoot 'test_ui.cjs') *> (Join-Path $build 'ui-test.txt');if($LASTEXITCODE -ne 0){throw 'UI test'}
& node (Join-Path $PSScriptRoot 'test_bridge.cjs') (Join-Path $build 'angle.exe') *> (Join-Path $build 'bridge-test.txt');if($LASTEXITCODE -ne 0){throw 'actual JS/C++ bridge'}
if($Mutations){
 foreach($m in @(
  @{name='raw-move-fallback';path=$owner;old='run_.request_joint_step(request,w.joint,{w.radians?robot_joint::StepUnit::CoreRadians:robot_joint::StepUnit::CadDegrees,w.angle})';new='run_.request(request)'},
  @{name='decimal-check-omitted';path=$wire;old='if(!decimal(f[11],w.angle))return false;';new='if(!decimal(f[11],w.angle))w.angle=1.;'}
 )){$s=Get-Content $m.path -Raw;if($s.Split(@($m.old),[StringSplitOptions]::None).Count-1-ne 1){throw 'mutation anchor'};$p=Join-Path $build "$($m.name).cpp";[IO.File]::WriteAllText($p,$s.Replace($m.old,$m.new));if($m.path-eq$owner){$results+=Compile-Run $m.name $p $wire $false}else{$results+=Compile-Run $m.name $owner $p $false}}
 $js=Get-Content (Join-Path $components 'robot_phone/web/app.js') -Raw
 $old='this.angleFence(context);';if($js.Split(@($old),[StringSplitOptions]::None).Count-1-ne 2){throw 'JS fence anchor'}
 $mutant=Join-Path $build 'await-fence-omitted.cjs';[IO.File]::WriteAllText($mutant,$js.Replace($old,''))
 & node --check $mutant; if($LASTEXITCODE-ne 0){throw 'JS mutant syntax'}
 $env:ANGLE_JS=$mutant
 try{& node (Join-Path $PSScriptRoot 'test_ui.cjs') *> (Join-Path $build 'await-fence-omitted-test.txt');$code=$LASTEXITCODE}finally{Remove-Item Env:ANGLE_JS}
 if($code-ne 1-or(Get-Content (Join-Path $build 'await-fence-omitted-test.txt') -Raw)-notmatch 'AssertionError'){throw 'JS mutation survived or errored'}
 $results+=[pscustomobject]@{name='await-fence-omitted';compile=0;exit=$code;positive=$false;source_hash=(Get-FileHash $mutant).Hash}
}
$results|ConvertTo-Json -Depth 4|Set-Content (Join-Path $build 'results.json') -Encoding utf8
Get-Content (Join-Path $build 'ui-test.txt'),(Join-Path $build 'bridge-test.txt')|Write-Host
