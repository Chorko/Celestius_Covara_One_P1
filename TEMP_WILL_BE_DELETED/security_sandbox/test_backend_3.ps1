param(
    $AdminEmail = ($env:TEST_ADMIN_EMAIL ?? "admin@demo.com"),
    $AdminPassword = ($env:TEST_ADMIN_PASSWORD ?? "demo1234")
)

$SupabaseUrl = ("https://ryrlyyqctjxyqzlysqqq.supabase.co")
if($env:SUPABASE_URL) { $SupabaseUrl = $env:SUPABASE_URL }
$SupabaseAnonKey = $env:SUPABASE_ANON_KEY

if (-not $SupabaseAnonKey) {
    Write-Warning "SUPABASE_ANON_KEY environment variable is required."
    exit 1
}

$body = @{ email = $AdminEmail; password = $AdminPassword } | ConvertTo-Json
$authResponse = Invoke-RestMethod -Uri "$SupabaseUrl/auth/v1/token?grant_type=password" -Method Post -Headers @{ "apikey" = $SupabaseAnonKey } -Body $body -ContentType "application/json"
$jwt = $authResponse.access_token

Write-Host "Running backend 3 (admin) tests..."
Invoke-RestMethod -Uri "$SupabaseUrl/rest/v1/audit_logs?select=*" -Headers @{ "apikey" = $SupabaseAnonKey; "Authorization" = "Bearer $jwt" } | Out-Null
Write-Host "Audit logs accessible."
