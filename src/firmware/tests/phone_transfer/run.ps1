param([switch]$Controls,[string]$BrowserPath=(Join-Path $env:ProgramFiles 'Google/Chrome/Application/chrome.exe'),[string]$NodeModules=(Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'))
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
$components=Join-Path $root 'src/firmware/components';$build=Join-Path $root '.dev/phone-transfer-evidence/build'
New-Item -ItemType Directory -Force $build|Out-Null
$env:NODE_PATH=$NodeModules;$env:PB_BROWSER=$BrowserPath
if(!(Test-Path -LiteralPath $BrowserPath)){throw 'Existing browser missing; no install performed'}
$env:ZIG_GLOBAL_CACHE_DIR=Join-Path $root '.dev/tools/zig-cache-global';$env:ZIG_LOCAL_CACHE_DIR=Join-Path $build 'cache'
$env:TEMP=Join-Path $build 'tmp';$env:TMP=$env:TEMP;New-Item -ItemType Directory -Force $env:TEMP|Out-Null
$original=[IO.File]::ReadAllText((Join-Path $PSScriptRoot '../phone_angle/test_angle.cpp'))
$anchor='static void parsing(){';if($original.Split(@($anchor),[StringSplitOptions]::None).Count-1-ne 1){throw 'fixture anchor'}
[IO.File]::WriteAllText((Join-Path $build 'angle_fixture.inc'),$original.Substring(0,$original.IndexOf($anchor)))
$exe=Join-Path $build 'bridge.exe';$argsList=@('c++','-std=c++17','-target','x86_64-windows-gnu','-O0','-g','-Wall','-Wextra','-Werror','-pedantic','-I',$build,'-I',(Join-Path $PSScriptRoot '../phone_angle'))
foreach($c in @('robot_phone','robot_boot','robot_run','robot_gate','robot_config','robot_can','robot_core')){$argsList+=@('-I',(Join-Path $components "$c/include"))}
foreach($f in @('robot_boot/supervisor.cpp','robot_boot/config_codec.cpp','robot_run/bench_run.cpp','robot_gate/control_gate.cpp','robot_config/codec.cpp','robot_can/stop_link.cpp','robot_core/stop_coordinator.cpp','robot_core/mks_codec.cpp','robot_phone/owner.cpp','robot_phone/wire.cpp')){$argsList+=Join-Path $components $f}
$argsList+=@((Join-Path $PSScriptRoot 'bridge.cpp'),'-o',$exe)
$argsList|ConvertTo-Json|Set-Content (Join-Path $build 'compile-command.json') -Encoding utf8
$ErrorActionPreference='Continue'
try{& (Join-Path $root '.dev/tools/zig-x86_64-windows-0.17.0/zig.exe') @argsList *> (Join-Path $build 'compile.txt');$code=$LASTEXITCODE}finally{$ErrorActionPreference='Stop'}
if($code-ne 0){Get-Content (Join-Path $build 'compile.txt');throw 'bridge compile'}
& $exe --test
if($LASTEXITCODE-ne 0){throw 'transfer actual core'}
exit 0
