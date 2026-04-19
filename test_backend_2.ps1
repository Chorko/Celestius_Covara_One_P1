$supabaseUrl = "https://aptgddoivrzpvpmydfyh.supabase.co"
$supabaseKey = "SUPABASE_ANON_KEY_REDACTED"
$authUrl = "$supabaseUrl/auth/v1/token?grant_type=password"

function Get-Token($email, $password) {
    $body = @{ email = $email; password = $password } | ConvertTo-Json
    try {
        $response = Invoke-RestMethod -Uri $authUrl -Method Post -Headers @{ "apikey" = $supabaseKey; "Content-Type" = "application/json" } -Body $body
        return $response.access_token
    } catch { return $null }
}

$workerToken = Get-Token "worker@demo.com" "demo1234"
$adminToken = Get-Token "admin@demo.com" "demo1234"
$baseUrl = "http://localhost:8000"

function Call-Api($token, $path) {
    try {
        $resp = Invoke-WebRequest -Uri "$baseUrl$path" -Method Get -Headers @{ "Authorization" = "Bearer $token"; "apikey" = $supabaseKey }
        $json = $resp.Content | ConvertFrom-Json
        return $json
    } catch {
        return $_.Exception.Response.StatusCode.value__
    }
}

$history = Call-Api $workerToken "/rewards/history"
$outbox = Call-Api $adminToken "/events/outbox/status"
$consumers = Call-Api $adminToken "/events/consumers/status"
$dlq = Call-Api $adminToken "/events/consumers/dead-letter?limit=10"
$worker_claims = Call-Api $adminToken "/workers/aaaa0000-0000-0000-0000-000000000201/claims?limit=5"

Write-Host "history_count: $(@($history).Count)"
Write-Host "outbox: $($outbox | ConvertTo-Json -Compress)"
Write-Host "consumers: $($consumers | ConvertTo-Json -Compress)"
Write-Host "dlq_count: $(@($dlq).Count)"
Write-Host "worker_claims_count: $(@($worker_claims).Count)"
