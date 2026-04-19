$supabaseUrl = "https://aptgddoivrzpvpmydfyh.supabase.co"
$anonKey = "SUPABASE_ANON_KEY_REDACTED"
function Get-Token($email, $password) {
    try {
        $loginUrl = "$supabaseUrl/auth/v1/token?grant_type=password"
        $body = @{ email = $email; password = $password } | ConvertTo-Json
        $headers = @{ "apikey" = $anonKey; "Content-Type" = "application/json" }
        $resp = Invoke-RestMethod -Uri $loginUrl -Method Post -Headers $headers -Body $body
        return $resp.access_token
    } catch { return $null }
}
function Call-API($url, $token) {
    try {
        $headers = @{ "Authorization" = "Bearer $token" }
        $response = Invoke-WebRequest -Uri $url -Headers $headers -Method Get -ErrorAction Stop
        return @{ Status = "Success"; Data = ($response.Content | ConvertFrom-Json) }
    } catch { return @{ Status = "Fail"; Error = $_.Exception.Message; URL = $url } }
}
$workerToken = Get-Token "worker@demo.com" "demo1234"
if ($workerToken) {
    $bal = Call-API "http://localhost:8000/rewards/balance" $workerToken
    $hist = Call-API "http://localhost:8000/rewards/history" $workerToken
    $me = Call-API "http://localhost:8000/workers/me" $workerToken
    Write-Host "Worker Balance: status=$($bal.Status), value=$($bal.Data.balance)"
    Write-Host "Worker History: status=$($hist.Status), count=$($hist.Data.history.Count)"
    Write-Host "Worker Profile: status=$($me.Status), zone_id=$($me.Data.preferred_zone_id)"
}
$adminToken = Get-Token "admin@demo.com" "demo1234"
if ($adminToken) {
    $claims = Call-API "http://localhost:8000/claims/?queue=all&page=1&page_size=5" $adminToken
    if ($claims.Status -eq "Success") {
        Write-Host "Admin Claims: status=Success, count=$($claims.Data.items.Count)"
        if ($claims.Data.items.Count -gt 0) {
            $id = $claims.Data.items[0].id
            $detail = Call-API "http://localhost:8000/claims/$id" $adminToken
            Write-Host "Claim Detail: status=$($detail.Status), id=$($detail.Data.id), payout_rec_present=$($null -ne $detail.Data.payout_recommendation)"
        }
    } else { Write-Host "Admin Claims: status=Fail, error=$($claims.Error)" }
}
