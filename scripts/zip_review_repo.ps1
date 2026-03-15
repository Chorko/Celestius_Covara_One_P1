# DEVTrails — Clean Review Zip Script (PowerShell)
# Creates a zip of the repo without .git/, .venv/, node_modules/, __pycache__/, etc.
# Usage: .\scripts\zip_review_repo.ps1

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$zipName  = "Celestius_DEVTrails_P1_review.zip"
$outPath  = Join-Path $repoRoot $zipName

# Patterns to exclude
$excludeDirs = @('.git', '.venv', 'venv', 'node_modules', '__pycache__', '.mypy_cache', '.pytest_cache', '.idea', '.vscode')

Write-Host "Creating clean review zip..."
Write-Host "  Source : $repoRoot"
Write-Host "  Output : $outPath"

# Collect files, excluding unwanted directories
$files = Get-ChildItem -Path $repoRoot -Recurse -File | Where-Object {
    $exclude = $false
    foreach ($dir in $excludeDirs) {
        if ($_.FullName -like "*\$dir\*") { $exclude = $true; break }
    }
    -not $exclude
}

# Remove old zip if it exists
if (Test-Path $outPath) { Remove-Item $outPath -Force }

# Create zip
$files | Compress-Archive -DestinationPath $outPath -Force

$count = $files.Count
$sizeMB = [math]::Round((Get-Item $outPath).Length / 1MB, 2)
Write-Host "Done. $count files, $sizeMB MB -> $zipName"
