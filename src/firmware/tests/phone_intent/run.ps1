param([switch]$Mutations)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
$components=Join-Path $root 'src/firmware/components'
$build=Join-Path $root '.dev/phone-intent-evidence/build'
$zig=Join-Path $root '.dev/tools/zig-x86_64-windows-0.17.0/zig.exe'
New-Item -ItemType Directory -Force $build|Out-Null
$env:ZIG_GLOBAL_CACHE_DIR=Join-Path $root '.dev/tools/zig-cache-global';$env:ZIG_LOCAL_CACHE_DIR=Join-Path $build 'cache'
$env:TEMP=Join-Path $build 'tmp';$env:TMP=$env:TEMP;New-Item -ItemType Directory -Force $env:TEMP|Out-Null
$exe=Join-Path $build 'bridge.exe'
$fixture=Get-Content (Join-Path $PSScriptRoot '../phone_angle/test_angle.cpp') -Raw -Encoding utf8
$anchor='static void parsing(){'
if($fixture.Split(@($anchor),[StringSplitOptions]::None).Count-1-ne 1){throw 'historical fixture anchor'}
$statusAnchor='static void status(AngleFixture& f)'
$bridgeAnchor='static void bridge(unsigned axis,bool measured)'
foreach($needle in @($statusAnchor,$bridgeAnchor)){if($fixture.Split(@($needle),[StringSplitOptions]::None).Count-1-ne 1){throw 'fixture status anchor'}}
$statusStart=$fixture.IndexOf($statusAnchor);$statusEnd=$fixture.IndexOf($bridgeAnchor)
[IO.File]::WriteAllText((Join-Path $build 'angle_fixture.inc'),$fixture.Substring(0,$fixture.IndexOf($anchor))+$fixture.Substring($statusStart,$statusEnd-$statusStart))
$argsList=@('c++','-std=c++17','-target','x86_64-windows-gnu','-O0','-g','-Wall','-Wextra','-Werror','-pedantic')
$argsList+=@('-I',$build,'-I',(Join-Path $PSScriptRoot '../phone_angle'))
foreach($c in @('robot_phone','robot_boot','robot_run','robot_gate','robot_config','robot_can','robot_core')){$argsList+=@('-I',(Join-Path $components "$c/include"))}
foreach($f in @('robot_boot/supervisor.cpp','robot_boot/config_codec.cpp','robot_run/bench_run.cpp','robot_gate/control_gate.cpp','robot_config/codec.cpp','robot_can/stop_link.cpp','robot_core/stop_coordinator.cpp','robot_core/mks_codec.cpp','robot_phone/owner.cpp','robot_phone/wire.cpp')){$argsList+=Join-Path $components $f}
$argsList+=@((Join-Path $PSScriptRoot 'bridge.cpp'),'-o',$exe)
$argsList|ConvertTo-Json|Set-Content (Join-Path $build 'compile-command.json') -Encoding utf8
$ErrorActionPreference='Continue'
try{& $zig @argsList *> (Join-Path $build 'compile.txt');$compileExit=$LASTEXITCODE}finally{$ErrorActionPreference='Stop'}
if($compileExit-ne 0){Get-Content (Join-Path $build 'compile.txt');throw 'bridge compile'}
& node --check (Join-Path $components 'robot_phone/web/app.js');if($LASTEXITCODE-ne 0){throw 'JS syntax'}
function Invoke-Node([string[]]$nodeArgs,[string]$log){$ErrorActionPreference='Continue';& node @nodeArgs *> $log;return $LASTEXITCODE}
$uiExit=Invoke-Node @((Join-Path $PSScriptRoot 'test_ui.cjs')) (Join-Path $build 'ui.txt');if($uiExit-ne 0){Get-Content (Join-Path $build 'ui.txt');throw 'UI positive'}
$bridgeExit=Invoke-Node @((Join-Path $PSScriptRoot 'test_bridge.cjs'),$exe) (Join-Path $build 'bridge.txt');if($bridgeExit-ne 0){Get-Content (Join-Path $build 'bridge.txt');throw 'actual bridge positive'}
$results=@([pscustomobject]@{name='positive';compile=0;ui=0;bridge=0;exe_sha256=(Get-FileHash $exe).Hash})
if($Mutations){
 $js=Get-Content (Join-Path $components 'robot_phone/web/app.js') -Raw -Encoding utf8
 foreach($m in @(
  @{name='global-capability-clear';old='previous.angle_available!==s.angle_available))this.cancelAngle();';new='previous.angle_available!==s.angle_available))this.clear();'},
  @{name='handoff-intent-erased';old='if(expected)h.phase=s.phase; else this.cancelHandoff();';new='if(expected)h.phase=s.phase; this.cancelHandoff();'},
  @{name='angle-revision-ignored';old='context.revision===this.angleRevision&&';new=''}
 )){
  if($js.Split(@($m.old),[StringSplitOptions]::None).Count-1-ne 1){throw "mutation anchor $($m.name)"}
  $mutant=Join-Path $build "$($m.name).cjs";[IO.File]::WriteAllText($mutant,$js.Replace($m.old,$m.new))
  & node --check $mutant;if($LASTEXITCODE-ne 0){throw 'mutant syntax'}
  $env:INTENT_JS=$mutant
  try{$code=Invoke-Node @((Join-Path $PSScriptRoot 'test_ui.cjs')) (Join-Path $build "$($m.name).txt")}finally{Remove-Item Env:INTENT_JS}
  if($code-ne 1-or(Get-Content (Join-Path $build "$($m.name).txt") -Raw)-notmatch 'AssertionError'){throw "mutant survived or non-assertion error $($m.name)"}
  $results+=[pscustomobject]@{name=$m.name;syntax=0;exit=$code;sha256=(Get-FileHash $mutant).Hash}
 }
}
$results|ConvertTo-Json -Depth 4|Set-Content (Join-Path $build 'results.json') -Encoding utf8
Get-Content (Join-Path $build 'ui.txt'),(Join-Path $build 'bridge.txt')|Write-Host
exit 0
