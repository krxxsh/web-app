Write-Host "🤖 Auto Commit System Running..." -ForegroundColor Cyan

# Check for changes
$changes = git status --porcelain

if (-not $changes) {
    Write-Host "✅ No changes to commit." -ForegroundColor Green
    exit
}

# Add all changes
git add .

# Commit with timestamp
$time = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
git commit -m "AI update: $time"

# Push to GitHub
git push origin main

Write-Host "🚀 Changes committed and pushed successfully!" -ForegroundColor Green