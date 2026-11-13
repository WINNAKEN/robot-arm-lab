$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'evidence.ps1')
$projectRoot=(Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
$components=Join-Path $projectRoot 'src/firmware/components'
$main=Join-Path $projectRoot 'src/firmware/main'
$build=Join-Path $projectRoot '.dev/phone-runtime-evidence/build'
$zig=Join-Path $projectRoot '.dev/tools/zig-x86_64-windows-0.17.0/zig.exe'
New-Item -ItemType Directory -Force $build | Out-Null
$env:ZIG_GLOBAL_CACHE_DIR=Join-Path $projectRoot '.dev/tools/zig-cache-global'
$env:ZIG_LOCAL_CACHE_DIR=Join-Path $build 'zig-cache-local'
$env:TEMP=Join-Path $build 'tmp';$env:TMP=$env:TEMP
New-Item -ItemType Directory -Force $env:TEMP | Out-Null
$assembly=''
foreach($asset in @(@{File='index.html';Symbol='index_html'},@{File='app.js';Symbol='app_js'})){
 $path=(Join-Path $components "robot_phone/web/$($asset.File)").Replace('\','/')
 $assembly+=".section .rdata`n.global _binary_$($asset.Symbol)_start`n.global _binary_$($asset.Symbol)_end`n_binary_$($asset.Symbol)_start:`n.incbin `"$path`"`n.byte 0`n_binary_$($asset.Symbol)_end:`n"
}
$assemblyPath=Join-Path $build 'http-assets.S';[IO.File]::WriteAllText($assemblyPath,$assembly)
$arguments=@('c++','-std=c++17','-target','x86_64-windows-gnu','-O0','-g','-Wall','-Wextra','-Werror','-pedantic','-I',(Join-Path $PSScriptRoot 'stub'),'-I',$main)
foreach($component in @('robot_phone','robot_boot','robot_run','robot_config','robot_gate','robot_can','robot_core')){$arguments+=@('-I',(Join-Path $components "$component/include"))}
$exe=Join-Path $build 'phone-http.exe';$arguments+=@((Join-Path $main 'phone_http.cpp'),(Join-Path $components 'robot_phone/wire.cpp'),(Join-Path $PSScriptRoot 'test_http.cpp'),$assemblyPath,'-o',$exe)
& $zig @arguments 2>&1|Out-File (Join-Path $build 'phone-http-compile.log') -Encoding utf8
if($LASTEXITCODE -ne 0){throw 'HTTP wrapper compile failed'}
& $exe 2>&1|Out-File (Join-Path $build 'phone-http-run.log') -Encoding utf8
$code=$LASTEXITCODE;Get-Content (Join-Path $build 'phone-http-run.log')|Write-Host
if($code -ne 0){throw "HTTP wrapper run failed $code"}
[pscustomobject]@{compile_exit=0;run_exit=$code;exe_sha256=(Get-FileHash $exe).Hash;production_wrapper='src/firmware/main/phone_http.cpp';network='NOT_RUN'}|ConvertTo-Json|Write-EvidenceText -Path (Join-Path $build 'phone-http-results.json')
