while ($true) {
    Write-Host "Checking for changes..." -ForegroundColor Yellow

    $changes = git status --porcelain

    if ($changes) {
        Write-Host "Changes detected! Auto committing..." -ForegroundColor Cyan

        git add .

        $time = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        $msg = "AI auto-update: $time"

        git commit -m $msg
        git push origin main
    }

    Start-Sleep -Seconds 60
}