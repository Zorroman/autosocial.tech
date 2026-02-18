param(
  [string]$ProdBase = "https://api.autosocial.tech",
  [string]$DevBase = "https://api-dev.autosocial.tech",
  [string]$AdminEmail = "admin@autosocial.local",
  [string]$AdminPassword = "admin12345",
  [string]$ExpectedProdRedirect = "https://api.autosocial.tech/api/integrations/meta/callback",
  [string]$ExpectedDevRedirect = "https://api-dev.autosocial.tech/api/integrations/meta/callback"
)

$ErrorActionPreference = 'Stop'
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$reportDir = "tests/reports"
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
$report = Join-Path $reportDir "smoke-$ts.txt"

function LogLine([string]$text) {
  $text | Tee-Object -FilePath $report -Append | Out-Null
}

function Invoke-Api([string]$Method, [string]$Url, [string]$Token = "", [string]$Body = "") {
  $tmp = New-TemporaryFile
  try {
    $args = @("-sS", "--connect-timeout", "8", "--max-time", "15", "-o", $tmp.FullName, "-w", "%{http_code}", "-X", $Method, $Url)
    if ($Token) { $args += @("-H", "Authorization: Bearer $Token") }
    if ($Body) { $args += @("-H", "Content-Type: application/json", "--data", $Body) }
    $code = (& curl.exe @args)
    $payload = Get-Content -Raw $tmp.FullName
    return @{ Code = [int]$code; Body = [string]$payload }
  }
  catch {
    return @{ Code = 0; Body = $_.Exception.Message }
  }
  finally {
    Remove-Item $tmp.FullName -Force -ErrorAction SilentlyContinue
  }
}

function Extract-JsonValue([string]$JsonRaw, [string]$Key) {
  try {
    $obj = $JsonRaw | ConvertFrom-Json
    return [string]$obj.$Key
  }
  catch {
    return ""
  }
}

function Get-Token([string]$Base) {
  $body = @{ email = $AdminEmail; password = $AdminPassword } | ConvertTo-Json -Compress
  $r = Invoke-Api -Method "POST" -Url "$Base/api/auth/login" -Body $body
  if ($r.Code -eq 200) {
    return (Extract-JsonValue -JsonRaw $r.Body -Key "token")
  }
  return ""
}

function Run-Suite([string]$Name, [string]$Base, [string]$ExpectedRedirect) {
  LogLine ""
  LogLine "===== $Name :: $Base ====="

  $h1 = Invoke-Api -Method "GET" -Url "$Base/health"
  LogLine "GET /health -> $($h1.Code)"
  LogLine $h1.Body

  $h2 = Invoke-Api -Method "GET" -Url "$Base/api/health"
  LogLine "GET /api/health -> $($h2.Code)"
  LogLine $h2.Body

  $token = Get-Token $Base
  if ($token) { LogLine "POST /api/auth/login -> 200" } else { LogLine "POST /api/auth/login -> failed (continue)" }

  $connect = Invoke-Api -Method "POST" -Url "$Base/api/integrations/meta/connect" -Token $token -Body "{}"
  LogLine "POST /api/integrations/meta/connect -> $($connect.Code)"
  LogLine $connect.Body
  if ($connect.Code -eq 200) {
    $redirect = Extract-JsonValue -JsonRaw $connect.Body -Key "redirect_uri"
    LogLine "redirect_uri(response): $redirect"
    if ($ExpectedRedirect -and $redirect -ne $ExpectedRedirect) {
      LogLine "WARN redirect mismatch expected=$ExpectedRedirect"
    }
  }

  $checks = @(
    @{ m = "GET"; p = "/api/integrations/meta/pages"; b = "" },
    @{ m = "POST"; p = "/api/integrations/meta/select-page"; b = '{"page_id":"dummy"}' },
    @{ m = "POST"; p = "/api/integrations/meta/test-post"; b = '{}' },
    @{ m = "POST"; p = "/api/integrations/meta/disconnect"; b = '{}' }
  )

  foreach ($c in $checks) {
    $r = Invoke-Api -Method $c.m -Url "$Base$($c.p)" -Token $token -Body $c.b
    LogLine "$($c.m) $($c.p) -> $($r.Code)"
    LogLine $r.Body
    if ($r.Code -eq 404) {
      LogLine "FAIL route missing: $($c.p)"
    }
  }
}

LogLine "AutoSocial smoke report"
LogLine "Generated: $(Get-Date -Format s)"
Run-Suite -Name "DEV" -Base $DevBase -ExpectedRedirect $ExpectedDevRedirect
Run-Suite -Name "PROD" -Base $ProdBase -ExpectedRedirect $ExpectedProdRedirect
LogLine ""
LogLine "Report saved: $report"
Write-Output $report
