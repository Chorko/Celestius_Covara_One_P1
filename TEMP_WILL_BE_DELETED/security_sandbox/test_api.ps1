$SupabaseUrl = ("https://ryrlyyqctjxyqzlysqqq.supabase.co")
if($env:SUPABASE_URL) { $SupabaseUrl = $env:SUPABASE_URL }
$SupabaseAnonKey = $env:SUPABASE_ANON_KEY

if (-not $SupabaseAnonKey) {
    Write-Warning "SUPABASE_ANON_KEY environment variable is required."
    exit 1
}

Write-Host "Verifying API health..."
$health = Invoke-RestMethod -Uri "$SupabaseUrl/rest/v1/" -Headers @{ "apikey" = $SupabaseAnonKey }
Write-Host "API is responsive."
