param (
    [string]$type,
    [string]$text
)

$base = "C:\Users\krish\Desktop\management\ai-data"

function Write-Memory {
    param ($folder, $file, $text)
    Add-Content "$base\$folder\$file" "
$text"
}

# Smart routing
if ($type -eq "task") {
    Write-Memory "memory" "tasks.md" "- $text"
}
elseif ($type -eq "bug") {
    Write-Memory "bugs" "bugs.md" "- $text"
}
elseif ($type -eq "idea") {
    Write-Memory "ideas" "ideas.md" "- $text"
}

# Always log
Write-Memory "logs" "activity.log" "$(Get-Date) - $text"
