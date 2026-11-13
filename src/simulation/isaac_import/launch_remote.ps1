param([Parameter(Mandatory=$true)][string]$PreparedRunJson)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$repoRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$evidence=Join-Path $repoRoot '.dev/isaac-import-evidence'
$current=Join-Path $evidence 'current.json'
function Save-Json($path,$value) { [IO.File]::WriteAllText($path,($value | ConvertTo-Json -Depth 12),(New-Object Text.UTF8Encoding($false))) }
function Invoke-Remote([string]$script) {
    $encoded=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($script))
    $answer=& ssh -o BatchMode=yes -o ConnectTimeout=10 $script:alias powershell -NoProfile -NonInteractive -EncodedCommand $encoded 2>> (Join-Path $evidence 'ssh-run-stderr.txt')
    if($LASTEXITCODE -ne 0) { throw "Remote command exit $LASTEXITCODE" }
    return ($answer -join "`n")
}
Save-Json $current ([ordered]@{status='BUILDING';phase='LAUNCHER_ENTRY';hardware_approved=$false})
$prepared=$null
try {
    $prepared=Get-Content -LiteralPath $PreparedRunJson -Raw -Encoding utf8 | ConvertFrom-Json
    if($prepared.run_id -notmatch '^[a-f0-9]{32}$') { throw 'Invalid generated run ID' }
    $localRun=Join-Path $repoRoot ('outputs/isaac-import-v1/runs/'+$prepared.run_id)
    if([IO.Path]::GetFullPath($prepared.local_run_dir) -ne [IO.Path]::GetFullPath($localRun)) { throw 'Unexpected local run path' }
    $config=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'remote_config.json') -Raw -Encoding utf8 | ConvertFrom-Json
    $script:alias=[string]$config.ssh_alias
    $remoteRun=([string]$config.remote_runs_root).TrimEnd('/')+'/'+$prepared.run_id
    if($remoteRun -ne $prepared.remote_run_dir -or $remoteRun -match "[\s'`"]" -or $config.isaac_root -match "[\s'`"]") { throw 'Unapproved/unsupported remote path' }
    $archive=Join-Path $localRun 'bundle.zip'
    if((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ine $prepared.bundle_sha256) { throw 'Local bundle drift' }
    $attemptFile=Join-Path $evidence 'attempts.json'
    $attempts=@()
    if(Test-Path -LiteralPath $attemptFile) { $attempts=@(Get-Content -LiteralPath $attemptFile -Raw -Encoding utf8 | ConvertFrom-Json) }
    if($attempts.Count -ge 2) { throw 'Author import attempt budget exhausted' }
    $setup=@'
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding
$dir='__RUN__'
if(@(Get-Process -Name kit,isaacsim -ErrorAction SilentlyContinue).Count -ne 0) { throw 'Existing Kit session; will not stop it' }
if(Test-Path -LiteralPath $dir) { throw 'Owned run already exists; no reuse' }
New-Item -ItemType Directory -Path $dir | Out-Null
[Console]::WriteLine('CREATED')
'@
    Invoke-Remote ($setup.Replace('__RUN__',$remoteRun)) | Out-Null
    & scp -q $archive ($script:alias+':'+$remoteRun+'/bundle.zip')
    if($LASTEXITCODE -ne 0) { throw 'Bundle transfer failed' }
    $expand=@'
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding
$dir='__RUN__'
if((Get-FileHash -LiteralPath ($dir+'/bundle.zip') -Algorithm SHA256).Hash -ine '__SHA__') { throw 'Transferred bundle digest mismatch' }
Expand-Archive -LiteralPath ($dir+'/bundle.zip') -DestinationPath $dir
[Console]::WriteLine('VERIFIED_EXPANDED')
'@
    Invoke-Remote ($expand.Replace('__RUN__',$remoteRun).Replace('__SHA__',$prepared.bundle_sha256)) | Out-Null
    $attempts+= [ordered]@{run_id=$prepared.run_id;remote_run_dir=$remoteRun;reserved_utc=[DateTime]::UtcNow.ToString('o');phase='STARTING'}
    [IO.File]::WriteAllText($attemptFile,(ConvertTo-Json -InputObject @($attempts) -Depth 8),(New-Object Text.UTF8Encoding($false)))
    Save-Json $current ([ordered]@{status='RUNNING';run_id=$prepared.run_id;remote_run_dir=$remoteRun;launch_mode='SSH_FOREGROUND_OWNED_PYTHON_SUPERVISOR';hardware_approved=$false})
    Write-Output ('Running owned Isaac job '+$prepared.run_id)
    $runScript=@'
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding
& '__PYTHON__' -B '__RUN__/supervise.py' --run-dir '__RUN__'
if($LASTEXITCODE -ne 0){throw 'Owned supervisor execution failed'}
'@
    $existingPython=([string]$config.isaac_root).TrimEnd('/')+'/kit/python/python.exe'
    $controller=Invoke-Remote ($runScript.Replace('__PYTHON__',$existingPython).Replace('__RUN__',$remoteRun))
    [IO.File]::WriteAllText((Join-Path $localRun 'supervisor-ssh-output.txt'),$controller)
    $retrieved=Join-Path $localRun 'retrieved'
    New-Item -ItemType Directory -Path $retrieved | Out-Null
    & scp -q -r ($script:alias+':'+$remoteRun) $retrieved
    if($LASTEXITCODE -ne 0) { throw 'Result retrieval failed' }
    $runCopy=Join-Path $retrieved $prepared.run_id
    $exit=Get-Content -LiteralPath (Join-Path $runCopy 'exit.json') -Raw -Encoding utf8 | ConvertFrom-Json
    if($exit.exit_code -ne 0) { throw ('Actual remote process failed: '+$exit.exit_code+'; logs preserved at '+$runCopy) }
    Save-Json $current ([ordered]@{status='READY_FOR_VALIDATION';run_id=$prepared.run_id;run_copy=$runCopy;remote_run_dir=$remoteRun;hardware_approved=$false})
    Write-Output ('Retrieved actual job '+$runCopy)
} catch {
    Save-Json $current ([ordered]@{status='FAILED';reason=$_.Exception.Message;run_id=$(if($prepared){$prepared.run_id}else{$null});hardware_approved=$false})
    throw
}
