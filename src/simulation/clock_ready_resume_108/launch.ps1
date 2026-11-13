param(
    [Parameter(Mandatory=$true)][ValidateSet('test','prepare','run','verify')][string]$Role,
    [string]$RunDir = '',
    [ValidateSet('','import','render_smoke','motion')][string]$Purpose = ''
)
$ErrorActionPreference = 'Stop'
try {
    $entry = Join-Path $PSScriptRoot 'driver.py'
    $digest = (Get-FileHash -LiteralPath $entry -Algorithm SHA256).Hash.ToLowerInvariant()
    $request = @{entry=$entry; sha256=$digest; role=$Role; run_dir=$RunDir; purpose=$Purpose} | ConvertTo-Json -Compress
    $data = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($request))
    $code = @"
import base64,hashlib,json,pathlib
a=json.loads(base64.b64decode('$data'))
p=pathlib.Path(a['entry']);b=p.read_bytes()
if hashlib.sha256(b).hexdigest()!=a['sha256']:raise SystemExit('Root changed before execution')
n={'__name__':'_checked069','__file__':str(p)}
exec(compile(b,str(p),'exec'),n)
raise SystemExit(n['public'](a['role'],a['run_dir'],a['purpose']))
"@
    $literal = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code))
    $python = Get-Command python.exe -CommandType Application | Where-Object Source -NotLike '*WindowsApps*' | Select-Object -First 1
    if ($null -eq $python) { throw 'Existing Python interpreter unavailable' }
    & $python.Source -I -B -c "import base64;exec(base64.b64decode('$literal'))"
    $childCode = $LASTEXITCODE
    if ($null -eq $childCode) { throw 'Python process did not report an exit code' }
    exit $childCode
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
