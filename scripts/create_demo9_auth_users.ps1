param(
  [switch]$Apply,
  [string]$Password = "Covara#2026!",
  [switch]$SkipVerify
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Read-DotEnvValue {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Key,
    [Parameter(Mandatory = $true)]
    [string]$EnvPath
  )

  if (-not (Test-Path $EnvPath)) {
    return $null
  }

  $pattern = "^\s*$([Regex]::Escape($Key))\s*=\s*(.*)\s*$"
  foreach ($line in Get-Content -Path $EnvPath) {
    if ($line -match '^\s*#') { continue }
    if ($line -match $pattern) {
      $value = $Matches[1]
      if ($value.StartsWith('"') -and $value.EndsWith('"')) {
        return $value.Trim('"')
      }
      return $value
    }
  }
  return $null
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $repoRoot ".env"

$supaUrl = $env:SUPABASE_URL
if ([string]::IsNullOrWhiteSpace($supaUrl)) {
  $supaUrl = $env:NEXT_PUBLIC_SUPABASE_URL
}
if ([string]::IsNullOrWhiteSpace($supaUrl)) {
  $supaUrl = Read-DotEnvValue -Key "NEXT_PUBLIC_SUPABASE_URL" -EnvPath $envPath
}

$anonKey = $env:SUPABASE_ANON_KEY
if ([string]::IsNullOrWhiteSpace($anonKey)) {
  $anonKey = $env:NEXT_PUBLIC_SUPABASE_ANON_KEY
}
if ([string]::IsNullOrWhiteSpace($anonKey)) {
  $anonKey = Read-DotEnvValue -Key "NEXT_PUBLIC_SUPABASE_ANON_KEY" -EnvPath $envPath
}

$serviceKey = $env:SUPABASE_SERVICE_ROLE_KEY
if ([string]::IsNullOrWhiteSpace($serviceKey)) {
  $serviceKey = Read-DotEnvValue -Key "SUPABASE_SERVICE_ROLE_KEY" -EnvPath $envPath
}

if ([string]::IsNullOrWhiteSpace($supaUrl) -or [string]::IsNullOrWhiteSpace($anonKey) -or [string]::IsNullOrWhiteSpace($serviceKey)) {
  throw "Missing SUPABASE URL/ANON/SERVICE_ROLE_KEY in environment or .env"
}

$users = @(
  @{ email = "demo.auto01@synthetic.covara.dev"; full_name = "DEMO9 AUTO01"; phone = "+919900000001" },
  @{ email = "demo.auto02@synthetic.covara.dev"; full_name = "DEMO9 AUTO02"; phone = "+919900000002" },
  @{ email = "demo.auto03@synthetic.covara.dev"; full_name = "DEMO9 AUTO03"; phone = "+919900000003" },
  @{ email = "demo.review01@synthetic.covara.dev"; full_name = "DEMO9 REVIEW01"; phone = "+919900000004" },
  @{ email = "demo.review02@synthetic.covara.dev"; full_name = "DEMO9 REVIEW02"; phone = "+919900000005" },
  @{ email = "demo.review03@synthetic.covara.dev"; full_name = "DEMO9 REVIEW03"; phone = "+919900000006" },
  @{ email = "demo.fraud01@synthetic.covara.dev"; full_name = "DEMO9 FRAUD01"; phone = "+919900000007" },
  @{ email = "demo.fraud02@synthetic.covara.dev"; full_name = "DEMO9 FRAUD02"; phone = "+919900000008" },
  @{ email = "demo.fraud03@synthetic.covara.dev"; full_name = "DEMO9 FRAUD03"; phone = "+919900000009" }
)

$modeLabel = "dry-run"
if ($Apply) {
  $modeLabel = "apply"
}
Write-Host "[info] mode=$modeLabel users=$($users.Count)"

if (-not $Apply) {
  foreach ($u in $users) {
    Write-Host "[dry-run] would create $($u.email) with email_confirm=true"
  }
  Write-Host "[hint] re-run with -Apply to execute"
  exit 0
}

$adminHeaders = @{
  "apikey" = $serviceKey
  "Authorization" = "Bearer $serviceKey"
  "Content-Type" = "application/json"
}

$created = 0
$exists = 0
$errors = @()

foreach ($u in $users) {
  $body = @{
    email = $u.email
    password = $Password
    email_confirm = $true
    user_metadata = @{
      role = "worker"
      full_name = $u.full_name
      phone = $u.phone
      seed_batch = "demo9"
    }
  } | ConvertTo-Json -Depth 8

  try {
    $null = Invoke-RestMethod -Method Post -Uri "$supaUrl/auth/v1/admin/users" -Headers $adminHeaders -Body $body
    $created++
    Write-Host "[created] $($u.email)"
  }
  catch {
    $resp = $_.Exception.Response
    if ($null -eq $resp) {
      $errors += "$($u.email): request_error=$($_.Exception.Message)"
      Write-Host "[error]   $($u.email) request error"
      continue
    }

    $statusCode = [int]$resp.StatusCode
    $reader = New-Object System.IO.StreamReader($resp.GetResponseStream())
    $respBody = $reader.ReadToEnd()

    if (($statusCode -eq 400 -or $statusCode -eq 422) -and ($respBody -match "already|registered|exists")) {
      $exists++
      Write-Host "[exists]  $($u.email)"
      continue
    }

    if ($respBody.Length -gt 220) {
      $respBody = $respBody.Substring(0, 220) + "..."
    }
    $errors += "$($u.email): http=$statusCode body=$respBody"
    Write-Host "[error]   $($u.email) -> http $statusCode"
  }
}

Write-Host "[result] created=$created existed=$exists errors=$($errors.Count)"
foreach ($e in $errors) {
  Write-Host "[create-error] $e"
}

if (-not $SkipVerify) {
  $anonHeaders = @{
    "apikey" = $anonKey
    "Authorization" = "Bearer $anonKey"
    "Content-Type" = "application/json"
  }

  $ok = 0
  $fails = @()

  foreach ($u in $users) {
    $loginBody = @{
      email = $u.email
      password = $Password
    } | ConvertTo-Json

    try {
      $null = Invoke-RestMethod -Method Post -Uri "$supaUrl/auth/v1/token?grant_type=password" -Headers $anonHeaders -Body $loginBody
      $ok++
      Write-Host "[login-ok]   $($u.email)"
    }
    catch {
      $resp = $_.Exception.Response
      if ($null -eq $resp) {
        $fails += "$($u.email): request_error=$($_.Exception.Message)"
        Write-Host "[login-fail] $($u.email) request error"
        continue
      }

      $statusCode = [int]$resp.StatusCode
      $reader = New-Object System.IO.StreamReader($resp.GetResponseStream())
      $respBody = $reader.ReadToEnd()
      if ($respBody.Length -gt 180) {
        $respBody = $respBody.Substring(0, 180) + "..."
      }
      $fails += "$($u.email): http=$statusCode body=$respBody"
      Write-Host "[login-fail] $($u.email) -> http $statusCode"
    }
  }

  Write-Host "[verify] login_ok=$ok/$($users.Count) failures=$($fails.Count)"
  foreach ($f in $fails) {
    Write-Host "[verify-fail] $f"
  }

  if ($errors.Count -gt 0 -or $fails.Count -gt 0) {
    exit 2
  }
}
else {
  if ($errors.Count -gt 0) {
    exit 2
  }
}

Write-Host "[done] DEMO9 users are created with Auto Confirm and login-ready."
exit 0
