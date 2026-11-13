param([switch]$Mutations,[ValidatePattern('^[a-zA-Z0-9_-]+$')][string]$Tag=('run-'+[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmssfff')))
$ErrorActionPreference='Stop'
$diagRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../../..'))
$diagBase=Join-Path $diagRoot '.dev/can-read-profile-evidence/build'
$diagBuild=Join-Path $diagBase $Tag
$diagCompiler=Join-Path $diagRoot '.dev/tools/zig-x86_64-windows-0.17.0/zig.exe'
$diagFirmware=Join-Path $diagRoot 'src/firmware'
if(Test-Path -LiteralPath $diagBuild){throw 'Use a new tag; preserve original test records'}
New-Item -ItemType Directory -Path $diagBuild | Out-Null
$env:ZIG_GLOBAL_CACHE_DIR=Join-Path $diagBase 'cache-global'
$env:ZIG_LOCAL_CACHE_DIR=Join-Path $diagBuild 'cache-local'
$env:TEMP=Join-Path $diagBuild 'tmp';$env:TMP=$env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
$diagComponent=Join-Path $diagFirmware 'components/robot_diagnostic'
$diagSource=Join-Path $diagComponent 'diagnostic.cpp'
$diagResults=@()
function Invoke-DiagnosticTest([string]$Label,[string]$Source,[bool]$ExpectedPass,[string]$ExtraInclude=''){
 $exe=Join-Path $diagBuild ($Label+'.exe')
 $extraArgs=@();if($ExtraInclude){$extraArgs=@('-I',$ExtraInclude)}
 & $diagCompiler c++ -std=c++17 -target x86_64-windows-gnu -O0 -g -Wall -Wextra -Werror -pedantic `
  @extraArgs `
  -I (Join-Path $diagComponent 'include') -I (Join-Path $diagFirmware 'components/robot_can/include') -I (Join-Path $diagFirmware 'components/robot_core/include') `
  $Source (Join-Path $diagFirmware 'components/robot_core/mks_codec.cpp') (Join-Path $PSScriptRoot 'test_diagnostic.cpp') -o $exe *> (Join-Path $diagBuild ($Label+'-compile.txt'))
 $compileCode=$LASTEXITCODE
 @{label=$Label;compile_exit=$compileCode} | ConvertTo-Json | Set-Content -Encoding utf8 -LiteralPath (Join-Path $diagBuild ($Label+'-compile-result.json'))
 if($compileCode -ne 0){Get-Content -LiteralPath (Join-Path $diagBuild ($Label+'-compile.txt')) -Tail 14;throw ($Label+' compile failed')}
 & $exe *> (Join-Path $diagBuild ($Label+'-run.txt'));$rc=$LASTEXITCODE
 $raw=Get-Content -Raw -LiteralPath (Join-Path $diagBuild ($Label+'-run.txt'))
 if($ExpectedPass){if($rc -ne 0 -or $raw -notmatch 'DIAGNOSTIC_HOST_PASS'){throw ($Label+' failed: '+$raw)}}
 elseif($rc -ne 1 -or $raw -notmatch 'CHECK FAILED:'){throw ($Label+' mutation not detected: '+$raw)}
 Write-Host ($Label+': '+$raw.Trim())
 return @{label=$Label;compile_exit=0;run_exit=$rc;expected_pass=$ExpectedPass;sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $exe).Hash.ToLowerInvariant()}
}
$diagResults+=Invoke-DiagnosticTest 'baseline' $diagSource $true
if($Mutations){
 $raw=Get-Content -Raw -LiteralPath $diagSource
 $variants=@(
 @{name='allow-write-opcode';from='code!=0x32) return false;';to='code!=0x32 && code!=0xF3) return false;'},
 @{name='ignore-hardware-approval';from='|| !p.hardware_approved ||';to='||'},
 @{name='allow-ten-ms-gap';from='now-last_poll_>=10';to='now-last_poll_>10'}
 )
 foreach($v in $variants){if(($raw.Split(@($v.from),[StringSplitOptions]::None).Count-1) -ne 1){throw ('Nonunique mutation anchor: '+$v.name)};$mutant=Join-Path $diagBuild ($v.name+'.cpp');[IO.File]::WriteAllText($mutant,$raw.Replace($v.from,$v.to));$diagResults+=Invoke-DiagnosticTest $v.name $mutant $false}
 $execution=Get-Content -Raw -LiteralPath (Join-Path $diagComponent 'include/robot_diagnostic/execution.hpp')
 $headerVariants=@(@{name='profile-physical-approval';from='p.transport.hardware_approved=false;';to='p.transport.hardware_approved=true;'},@{name='cadence-allows-ten-ms';from='now-last_service_>=10';to='now-last_service_>10'})
 foreach($v in $headerVariants){
  if(($execution.Split(@($v.from),[StringSplitOptions]::None).Count-1) -ne 1){throw ('Nonunique header mutation: '+$v.name)}
  $override=Join-Path $diagBuild $v.name;$headerDir=Join-Path $override 'robot_diagnostic';New-Item -ItemType Directory -Path $headerDir -Force | Out-Null
  [IO.File]::WriteAllText((Join-Path $headerDir 'execution.hpp'),$execution.Replace($v.from,$v.to))
  $diagResults+=Invoke-DiagnosticTest $v.name $diagSource $false $override
 }
}
@{status='HOST_ONLY_PASS';hardware=$false;flash=$false;results=$diagResults} | ConvertTo-Json -Depth 6 | Set-Content -Encoding utf8 -LiteralPath (Join-Path $diagBuild 'result.json')
