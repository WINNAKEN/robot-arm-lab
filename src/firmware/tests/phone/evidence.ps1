# Bounded retry applies only to local evidence-file sharing violations, never
# control requests, compiler results or a failed test execution.
function Write-EvidenceText {
 [CmdletBinding()]
 param([Parameter(Mandatory=$true)][string]$Path,[Parameter(Mandatory=$true,ValueFromPipeline=$true)][string]$Text)
 process {
  for($attempt=0;$attempt -lt 5;$attempt++){
   try{[IO.File]::WriteAllText($Path,$Text,[Text.UTF8Encoding]::new($false));return}
   catch [IO.IOException]{
    Write-Warning "Evidence sharing failure attempt=$($attempt+1) path=$Path error=$($_.Exception.Message)"
    if($attempt -eq 4){throw}
    Start-Sleep -Milliseconds 100
   }
  }
 }
}
