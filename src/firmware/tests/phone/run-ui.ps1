$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'evidence.ps1')
$projectRoot=(Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
$build=Join-Path $projectRoot '.dev/phone-runtime-evidence/build'
& node (Join-Path $PSScriptRoot 'test_ui.cjs') 2>&1|Out-File (Join-Path $build 'phone-ui-run.log') -Encoding utf8
$code=$LASTEXITCODE;Get-Content (Join-Path $build 'phone-ui-run.log')|Write-Host
if($code -ne 0){throw "UI model failed $code"}
[pscustomobject]@{node=(& node --version);exit=$code;source_sha256=(Get-FileHash (Join-Path $projectRoot 'src/firmware/components/robot_phone/web/app.js')).Hash;browser='NOT_RUN'}|ConvertTo-Json|Write-EvidenceText -Path (Join-Path $build 'phone-ui-results.json')
