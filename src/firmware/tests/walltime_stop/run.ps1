param()
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
$components=Join-Path $root 'src/firmware/components'
$build=Join-Path $root '.dev/walltime-stop-evidence/build'
New-Item -ItemType Directory -Force $build | Out-Null
$env:ZIG_GLOBAL_CACHE_DIR=Join-Path $root '.dev/tools/zig-cache-global'
$env:ZIG_LOCAL_CACHE_DIR=Join-Path $build 'cache'
$env:TEMP=Join-Path $build 'tmp';$env:TMP=$env:TEMP
New-Item -ItemType Directory -Force $env:TEMP | Out-Null
$argsList=@('c++','-std=c++17','-target','x86_64-windows-gnu','-O0','-g','-Wall','-Wextra','-Werror','-pedantic','-I',(Join-Path $PSScriptRoot '../phone_angle'))
foreach($c in @('robot_phone','robot_boot','robot_run','robot_gate','robot_config','robot_can','robot_core')){$argsList+=@('-I',(Join-Path $components "$c/include"))}
foreach($f in @('robot_boot/supervisor.cpp','robot_boot/config_codec.cpp','robot_run/bench_run.cpp','robot_gate/control_gate.cpp','robot_config/codec.cpp','robot_can/stop_link.cpp','robot_core/stop_coordinator.cpp','robot_core/mks_codec.cpp','robot_phone/owner.cpp','robot_phone/wire.cpp')){$argsList+=Join-Path $components $f}
$argsList+=@((Join-Path $PSScriptRoot 'bridge.cpp'),'-o',(Join-Path $build 'bridge.exe'))
$argsList|ConvertTo-Json|Set-Content (Join-Path $build 'compile-command.json') -Encoding utf8
& (Join-Path $root '.dev/tools/zig-x86_64-windows-0.17.0/zig.exe') @argsList *> (Join-Path $build 'compile.txt')
if($LASTEXITCODE -ne 0){throw 'Walltime native strict compile failed'}
Write-Output 'PASS walltime native strict compile; no runtime/hardware claim'
