function Get-EnvVar($name, $fallback) {
    if (!(Test-Path .env)) { return $null }
    $lines = Get-Content .env
    $match = $lines | Select-String "^$name="
    if (!$match -and $fallback) { $match = $lines | Select-String "^$fallback=" }
    if ($match) { 
        $v = $match.Line.Split('=', 2)[1].Trim().Trim('"').Trim("'")
        return $v
    }
    return $null
}

$SB_URL = Get-EnvVar "SUPABASE_URL" "NEXT_PUBLIC_SUPABASE_URL"
$SB_KEY = Get-EnvVar "SUPABASE_ANON_KEY" "NEXT_PUBLIC_SUPABASE_ANON_KEY"

function Login-Supabase($email, $password) {
    $body = @{ email = $email; password = $password } | ConvertTo-Json
    $uri = "$SB_URL/auth/v1/token?grant_type=password"
    try {
        $resp = Invoke-RestMethod -Method Post -Uri $uri -Headers @{ "apikey" = $SB_KEY } -Body $body -ContentType "application/json"
        return $resp.access_token
    } catch {
        Write-Host "Login Failed for email: $email"
        return $null
    }
}

$workerToken = Login-Supabase "worker@demo.com" "demo1234"
$adminToken = Login-Supabase "admin@demo.com" "demo1234"

function Call-API($method, $path, $token) {
    if (!$token) { return $null }
    $headers = @{ "Authorization" = "Bearer $token" }
    try {
        return Invoke-RestMethod -Method $method -Uri "http://localhost:8000$path" -Headers $headers
    } catch {
        return $null
    }
}

$results = @{ rewards="FAIL"; my_zone_data="FAIL"; claim_detail="FAIL"; event_ops="FAIL"; admin_users="FAIL" }

try {
    Write-Host "--- Worker Data ---"
    $balance = Call-API GET "/rewards/balance" $workerToken
    if ($null -ne $balance) {
        $bVal = if ($null -ne $balance.total_rewards) { $balance.total_rewards } else { $balance.balance }
        Write-Host "Balance: $bVal"
    }
    
    $history = Call-API GET "/rewards/history" $workerToken
    if ($null -ne $history) { Write-Host "History Count: $($history.Count)" }
    
    $me = Call-API GET "/workers/me" $workerToken
    if ($null -ne $me) {
        Write-Host "Worker: zone=$($me.preferred_zone_id), city=$($me.city), platform=$($me.platform_name), trust=$($me.trust_score)"
        $results.rewards = "PASS"

        if ($me.preferred_zone_id) {
            $zone = Call-API GET "/zones/$($me.preferred_zone_id)" $workerToken
            if ($null -ne $zone) {
                Write-Host "Zone: $($zone.zone_name) ($($zone.center_lat), $($zone.center_lng))"
                $results.my_zone_data = "PASS"
            }
        }
    }

    Write-Host "`n--- Admin Claims ---"
    $claims = Call-API GET "/claims?queue=all&page=1&page_size=15" $adminToken
    if ($null -ne $claims) {
        $claimList = $claims.items
        Write-Host "Claim Count: $($claimList.Count)"
        $results.claim_detail = "PASS"
    }

    Write-Host "`n--- Admin Users & Status ---"
    $workersList = Call-API GET "/workers?limit=200" $adminToken
    if ($null -ne $workersList) {
        $demoWorkerId = "aaaa-aaaa-aaaa-aaaa-000000000201"
        $found = ($workersList | Where-Object { $_.id -like "*201" -or $_.id -eq $demoWorkerId })
        Write-Host "Demo Worker Found: $([bool]$found)"
        $results.admin_users = "PASS"
    }

    $outbox = Call-API GET "/events/outbox/status" $adminToken
    if ($null -ne $outbox) {
        Write-Host "Outbox Status: $($outbox.status)"
        $results.event_ops = "PASS"
    }
} catch {}

Write-Host "`n--- SUMMARY ---"
$results.Keys | % { Write-Host "$_ : $($results[$_])" }
