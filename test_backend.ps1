$supabaseUrl = "https://aptgddoivrzpvpmydfyh.supabase.co"
$supabaseKey = "SUPABASE_ANON_KEY_REDACTED"
$workerEmail = "worker@demo.com"
$adminEmail = "admin@demo.com"
$pwd = "demo1234"
$authUrl = "$supabaseUrl/auth/v1/token?grant_type=password"

function Get-AuthResponse($email, $password) {
    $body = @{ email = $email; password = $password } | ConvertTo-Json
    try {
        return Invoke-RestMethod -Uri $authUrl -Method Post -Headers @{ "apikey" = $supabaseKey; "Content-Type" = "application/json" } -Body $body
    } catch {
        Write-Host "Auth Error for $email: $($_.Exception.Message)"
        return $null
    }
}

$workerAuth = Get-AuthResponse $workerEmail $pwd
$adminAuth = Get-AuthResponse $adminEmail $pwd

$baseUrl = "http://localhost:8000"

function Call-Api($token, $path) {
    try {
        $resp = Invoke-WebRequest -Uri "$baseUrl$path" -Method Get -Headers @{ "Authorization" = "Bearer $token"; "apikey" = $supabaseKey }
        return $resp.Content | ConvertFrom-Json
    } catch {
        $status = if ($_.Exception.Response) { $_.Exception.Response.StatusCode.value__ } else { "Unknown" }
        Write-Host "Endpoint $path failed: $status"
        return $null
    }
}

Write-Host "--- Worker Results ---"
if ($null -ne $workerAuth) {
    $tk = $workerAuth.access_token
    # 1. Balance
    $res = Call-Api $tk "/rewards/balance"
    if ($null -ne $res) { Write-Host "Balance: $($res.balance)" }
    # 2. History
    $res = Call-Api $tk "/rewards/history"
    if ($null -ne $res) { Write-Host "History count: $($res.Count)" }
    # 3. Me
    $res = Call-Api $tk "/workers/me"
    if ($null -ne $res) { 
        Write-Host "preferred_zone_id: $($res.preferred_zone_id)"
        Write-Host "city: $($res.city)"
        Write-Host "platform_name: $($res.platform_name)"
        $zoneId = $res.preferred_zone_id
        # 4. Zone
        if ($zoneId) {
            $res = Call-Api $tk "/zones/$zoneId"
            if ($null -ne $res) {
                Write-Host "zone_name: $($res.zone_name)"
                Write-Host "center_lat: $($res.center_lat)"
                Write-Host "center_lng: $($res.center_lng)"
            }
        }
    }
}

Write-Host "`n--- Admin Results ---"
if ($null -ne $adminAuth) {
    $tk = $adminAuth.access_token
    # 1. Claims listing
    $res = Call-Api $tk "/claims?queue=all&page=1&page_size=5"
    if ($null -ne $res) {
        Write-Host "claims_total: $($res.total)"
        $cnt = if ($res.items) { $res.items.Count } else { 0 }
        Write-Host "claims_page_count: $cnt"
        if ($cnt -gt 0) {
            $firstClaimId = $res.items[0].id
            Write-Host "first_claim_id: $firstClaimId"
            # 2. Claim Detail
            $res2 = Call-Api $tk "/claims/$firstClaimId"
            if ($null -ne $res2) {
                Write-Host "claim_detail_success: True"
                Write-Host "has_payout_recommendation: $( $null -ne $res2.payout_recommendation )"
                Write-Host "has_review_meta: $( $null -ne $res2.review_meta )"
            }
        }
    }
    # 3. Outbox status
    $res = Call-Api $tk "/events/outbox/status"
    if ($null -ne $res) { Write-Host "outbox_status_counts: $($res | ConvertTo-Json -Compress)" }
    # 4. Consumer status
    $res = Call-Api $tk "/events/consumers/status"
    if ($null -ne $res) { Write-Host "consumer_status_counts: $($res | ConvertTo-Json -Compress)" }
    # 5. DLQ
    $res = Call-Api $tk "/events/consumers/dead-letter?limit=10"
    if ($null -ne $res) { Write-Host "dlq_count: $($res.Count)" }
    # 6. Workers
    $res = Call-Api $tk "/workers?limit=5"
    if ($null -ne $res) { 
        Write-Host "workers_count: $($res.Count)"
        if ($res.Count -gt 0) { Write-Host "first_worker_profile_id: $($res[0].profile_id)" }
    }
    # 7. Specific worker claims
    $swid = "aaaa0000-0000-0000-0000-000000000201"
    $res = Call-Api $tk "/workers/$swid/claims?limit=5"
    if ($null -ne $res) { Write-Host "specific_worker_claims_count: $($res.Count)" }
}
