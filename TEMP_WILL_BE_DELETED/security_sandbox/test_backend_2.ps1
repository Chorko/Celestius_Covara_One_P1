param(
    $WorkerEmail = ($env:TEST_WORKER_EMAIL ?? "worker@demo.com"),
    $WorkerPassword = ($env:TEST_WORKER_PASSWORD ?? "demo1234")
)

$SupabaseUrl = ("https://ryrlyyqctjxyqzlysqqq.supabase.co")
if($env:SUPABASE_URL) { $SupabaseUrl = $env:SUPABASE_URL }
$SupabaseAnonKey = $env:SUPABASE_ANON_KEY

if (-not $SupabaseAnonKey) {
    Write-Warning "SUPABASE_ANON_KEY environment variable is required."
    exit 1
}

$body = @{ email = $WorkerEmail; password = $WorkerPassword } | ConvertTo-Json
$authResponse = Invoke-RestMethod -Uri "$SupabaseUrl/auth/v1/token?grant_type=password" -Method Post -Headers @{ "apikey" = $SupabaseAnonKey } -Body $body -ContentType "application/json"
$jwt = $authResponse.access_token

Write-Host "Running backend 2 tests with worker JWT..."
Invoke-RestMethod -Uri "$SupabaseUrl/rest/v1/profiles?select=*" -Headers @{ "apikey" = $SupabaseAnonKey; "Authorization" = "Bearer $jwt" } | Out-Null
Write-Host "Success."
