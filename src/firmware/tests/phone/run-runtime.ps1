param([switch]$Mutations)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'evidence.ps1')
$projectRoot=(Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
$components=Join-Path $projectRoot 'src/firmware/components'
$build=Join-Path $projectRoot '.dev/phone-runtime-evidence/build'
$zig=Join-Path $projectRoot '.dev/tools/zig-x86_64-windows-0.17.0/zig.exe'
New-Item -ItemType Directory -Force $build | Out-Null
$env:ZIG_GLOBAL_CACHE_DIR=Join-Path $projectRoot '.dev/tools/zig-cache-global'
$env:ZIG_LOCAL_CACHE_DIR=Join-Path $build 'zig-cache-local'
$env:TEMP=Join-Path $build 'tmp';$env:TMP=$env:TEMP
New-Item -ItemType Directory -Force $env:TEMP | Out-Null
function Run-Phone([string]$Name,[string]$Owner,[bool]$Expected){
 $arguments=@('c++','-std=c++17','-target','x86_64-windows-gnu','-O0','-g','-Wall','-Wextra','-Werror','-pedantic','-I',(Join-Path $PSScriptRoot 'runtime_stub'),'-I',(Join-Path $PSScriptRoot 'stub'))
 foreach($component in @('robot_phone','robot_config','robot_boot','robot_run','robot_gate','robot_can','robot_core')){$arguments+=@('-I',(Join-Path $components "$component/include"))}
 foreach($file in @('robot_phone/wire.cpp','robot_boot/supervisor.cpp','robot_boot/config_codec.cpp','robot_run/bench_run.cpp','robot_config/codec.cpp','robot_gate/control_gate.cpp','robot_can/stop_link.cpp','robot_core/stop_coordinator.cpp','robot_core/mks_codec.cpp')){$arguments+=Join-Path $components $file}
 $exe=Join-Path $build "$Name.exe";$arguments+=@($Owner,(Join-Path $PSScriptRoot 'test_runtime_wrapper.cpp'),'-o',$exe)
 & $zig @arguments 2>&1|Out-File (Join-Path $build "$Name-compile.log") -Encoding utf8
 if($LASTEXITCODE -ne 0){throw "$Name compile failed: $(Join-Path $build "$Name-compile.log")"}
 & $exe 2>&1|Out-File (Join-Path $build "$Name-run.log") -Encoding utf8
 $code=$LASTEXITCODE;Get-Content (Join-Path $build "$Name-run.log")|Write-Host
 if(($Expected -and $code -ne 0)-or(!$Expected -and $code -eq 0)){throw "$Name unexpected exit=$code"}
 [pscustomobject]@{name=$Name;compile_exit=0;run_exit=$code;expected_pass=$Expected;exe_sha256=(Get-FileHash $exe).Hash}
}

Run-Phone 'phone-runtime-wrapper' (Join-Path $components 'robot_phone/owner.cpp') $true | ConvertTo-Json | Write-EvidenceText -Path (Join-Path $build 'phone-runtime-wrapper-results.json')
