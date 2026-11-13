param([switch]$PrepareOnly,[ValidateSet('solver','solver_pd')][string]$Variant='solver')
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$repoRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$out=Join-Path $repoRoot 'outputs/isaac-settling-v1'
$evidence=Join-Path $out 'evidence'
[IO.Directory]::CreateDirectory($evidence) | Out-Null
$lock=$null
function Save-Json($path,$value) {
    [IO.File]::WriteAllText($path,($value | ConvertTo-Json -Depth 15),(New-Object Text.UTF8Encoding($false)))
}
function Assert-SecondAttemptEligible($prior,[string]$variant) {
    if($null -eq $prior -or $prior.status -eq 'INVALID_EVIDENCE') {
        throw 'No automatic retry without complete valid prior dynamics evidence'
    }
    if($prior.status -eq 'GRAVITY_COLLISION_MOTION_PASS') { throw 'Successful experiment must not be repeated' }
    if($prior.status -ne 'DYNAMICS_FAILED' -or $variant -ne 'solver_pd' -or
       $prior.evidence_valid -isnot [bool] -or $prior.evidence_valid -cne $true -or
       $prior.full_frame_samples -ne 6781 -or $prior.checkpoints_passed -isnot [int] -or
       $prior.checkpoints_passed -lt 0 -or $prior.checkpoints_passed -ge 28 -or
       $prior.tracking_failures -isnot [array] -or $prior.dynamic_failures -isnot [array] -or
       @($prior.tracking_failures).Count -ne (28-$prior.checkpoints_passed) -or
       @($prior.tracking_failures | Sort-Object -Unique).Count -ne @($prior.tracking_failures).Count -or
       @($prior.tracking_failures | Where-Object { $_ -isnot [string] -or $_.Length -eq 0 }).Count -ne 0 -or
       @($prior.dynamic_failures).Count -ne 0) {
        throw 'PD retry requires valid complete isolated settling failure and no contact/feedforward failure'
    }
}
function Remote([string]$script) {
    $encoded=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($script))
    $answer=& ssh -o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=15 -o ServerAliveCountMax=10 $script:alias powershell -NoProfile -NonInteractive -EncodedCommand $encoded 2>> (Join-Path $evidence 'ssh-stderr.txt')
    if($LASTEXITCODE -ne 0) { throw "SSH command failed: $LASTEXITCODE" }
    return ($answer -join "`n")
}
$prepared=$null
$current=Join-Path $out 'current.json'
$lockPath=Join-Path $evidence 'launch.lock'
try {
    $lock=[IO.File]::Open($lockPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    Save-Json $current ([ordered]@{status='BUILDING';phase='PREPARE';hardware_approved=$false})
    $text=& py -B (Join-Path $PSScriptRoot 'runtime.py') prepare --root $repoRoot --variant $Variant
    if($LASTEXITCODE -ne 0) { throw 'Local preparation failed' }
    $prepared=($text -join "`n") | ConvertFrom-Json
    $localRun=Join-Path $out ('runs/'+$prepared.run_id)
    if($prepared.run_id -notmatch '^[0-9a-f]{32}$' -or [IO.Path]::GetFullPath($prepared.local_run_dir) -ne [IO.Path]::GetFullPath($localRun)) { throw 'Unexpected prepared run path' }
    if($PrepareOnly) {
        Save-Json $current ([ordered]@{status='PREPARED_NOT_RUN';run_id=$prepared.run_id;hardware_approved=$false})
        Write-Output ('Prepared only: '+$localRun)
        return
    }
    $config=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'pins.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $script:alias=[string]$config.ssh_alias
    if($script:alias -notmatch '^[A-Za-z0-9_-]+$') { throw 'Unsupported SSH alias' }
    $remoteRun=([string]$config.remote_runs_root).TrimEnd('/')+'/'+$prepared.run_id
    foreach($path in @($remoteRun,[string]$config.isaac_root)) {
        if($path -notmatch '^[A-Za-z]:/[A-Za-z0-9_/-]+$') { throw 'Unsupported remote path' }
    }
    if($remoteRun -ne $prepared.remote_run_dir -or $config.hardware_approved -ne $false -or $config.maximum_author_attempts -ne 2) { throw 'Scope/config mismatch' }
    $attemptFile=Join-Path $evidence 'attempts.json'
    $attempts=@()
    if(Test-Path -LiteralPath $attemptFile) { $attempts=@(Get-Content -LiteralPath $attemptFile -Raw -Encoding UTF8 | ConvertFrom-Json) }
    if($attempts.Count -ge 2) { throw 'Finite 047 author dynamic run budget exhausted' }
    if($attempts.Count -eq 0 -and $Variant -ne 'solver') { throw 'First attempt must isolate the solver change' }
    if($attempts.Count -eq 1) {
        $prior=Join-Path $out ('runs/'+$attempts[0].run_id+'/retrieved/'+$attempts[0].run_id+'/validation.json')
        $priorResult=$null
        if(Test-Path -LiteralPath $prior) {
            & py -B (Join-Path $PSScriptRoot 'verify.py') --run-dir (Split-Path $prior -Parent) --root $repoRoot
            if($LASTEXITCODE -notin @(0,2)) { throw 'Prior raw evidence did not revalidate; no retry' }
            $priorResult=Get-Content -LiteralPath $prior -Raw -Encoding UTF8 | ConvertFrom-Json
        }
        Assert-SecondAttemptEligible $priorResult $Variant
    }
    $attempts+=[ordered]@{run_id=$prepared.run_id;variant=$Variant;reserved_utc=[DateTime]::UtcNow.ToString('o');remote_run_dir=$remoteRun;phase='RESERVED_BEFORE_REMOTE_START'}
    Save-Json $attemptFile @($attempts)
    $preflight=@'
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding
if(@(Get-Process -Name kit,isaacsim -ErrorAction SilentlyContinue).Count -ne 0) { throw 'Existing Kit session; will not stop it' }
if((([IO.File]::ReadAllText('__ISAAC__/VERSION')).Trim()) -ne '__VERSION__') { throw 'Isaac version drift' }
if(Test-Path -LiteralPath '__RUN__') { throw 'Run exists; no overwrite' }
New-Item -ItemType Directory -Path '__RUN__' | Out-Null
[Console]::WriteLine('NEW_OWNED_RUN')
'@
    Remote ($preflight.Replace('__RUN__',$remoteRun).Replace('__ISAAC__',[string]$config.isaac_root).Replace('__VERSION__',[string]$config.expected_isaac_version)) | Out-Null
    $archive=Join-Path $localRun 'bundle.zip'
    if((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ine $prepared.bundle_sha256) { throw 'Bundle drift' }
    & scp -q $archive ($script:alias+':'+$remoteRun+'/bundle.zip')
    if($LASTEXITCODE -ne 0) { throw 'Transfer failed' }
    $expand=@'
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
if((Get-FileHash -LiteralPath '__RUN__/bundle.zip' -Algorithm SHA256).Hash -ine '__SHA__') { throw 'Transfer hash mismatch' }
Expand-Archive -LiteralPath '__RUN__/bundle.zip' -DestinationPath '__RUN__'
[Console]::WriteLine('VERIFIED')
'@
    Remote ($expand.Replace('__RUN__',$remoteRun).Replace('__SHA__',$prepared.bundle_sha256)) | Out-Null
    Save-Json $current ([ordered]@{status='RUNNING';run_id=$prepared.run_id;remote_run_dir=$remoteRun;hardware_approved=$false})
    Write-Output ('Running finite simulation '+$prepared.run_id)
    $launch=@'
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding
& '__ISAAC__/kit/python/python.exe' -B '__RUN__/runtime.py' supervise --run-dir '__RUN__'
[Console]::WriteLine('SUPERVISOR_RETURNED_'+$LASTEXITCODE)
'@
    $answer=Remote ($launch.Replace('__RUN__',$remoteRun).Replace('__ISAAC__',[string]$config.isaac_root))
    [IO.File]::WriteAllText((Join-Path $localRun 'ssh-supervisor.txt'),$answer)
    $retrieved=Join-Path $localRun 'retrieved'
    [IO.Directory]::CreateDirectory($retrieved) | Out-Null
    & scp -q -r ($script:alias+':'+$remoteRun) $retrieved
    if($LASTEXITCODE -ne 0) { throw 'Raw result retrieval failed' }
    $runCopy=Join-Path $retrieved $prepared.run_id
    $exit=Get-Content -LiteralPath (Join-Path $runCopy 'exit.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if($exit.exit_code -ne 0) { throw ('Actual simulator failed '+$exit.exit_code+'; logs: '+$runCopy) }
    & py -B (Join-Path $PSScriptRoot 'verify.py') --run-dir $runCopy --root $repoRoot
    if($LASTEXITCODE -ne 0) { throw ('Runtime verification failed; inspect '+$runCopy+'/validation.json') }
    Save-Json $current ([ordered]@{status='AUTHOR_RUNTIME_VERIFIED';run_id=$prepared.run_id;run_copy=$runCopy;hardware_approved=$false;independent_review='PENDING'})
    Write-Output ('Simulation data verified: '+$runCopy)
} catch {
    if($null -ne $lock) {
        Save-Json $current ([ordered]@{status='FAILED';run_id=$(if($prepared){$prepared.run_id}else{$null});reason=$_.Exception.Message;hardware_approved=$false})
    }
    throw
} finally {
    if($null -ne $lock) {
        $lock.Dispose()
        Remove-Item -LiteralPath $lockPath
    }
}
