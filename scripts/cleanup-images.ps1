# Docker Image Cleanup Script
# This script removes old Docker images to prevent accumulation of too many tags locally

param(
    [int]$MaxImages = 10,
    [string[]]$ImagePrefixes = @("mosquitto", "simulator", "frontend", "backend", "ingestor", "spark", "grafana", "prometheus")
)

Write-Host "Starting Docker image cleanup..." -ForegroundColor Green

foreach ($prefix in $ImagePrefixes) {
    Write-Host "Checking images for: $prefix" -ForegroundColor Yellow
    
    # Get all images for this prefix using simple docker images command
    $allDockerImages = docker images --format "{{.Repository}}:{{.Tag}}`t{{.ID}}`t{{.CreatedAt}}" | Where-Object { $_ -ne "" }
    
    # Filter for images matching our prefix
    $images = @()
    foreach ($line in $allDockerImages) {
        $parts = $line -split "`t"
        if ($parts.Length -eq 3) {
            $repoTag = $parts[0]
            $imageId = $parts[1] 
            $createdAt = $parts[2]
            
            # Check if this image matches our prefix
            if ($repoTag -like "$prefix*" -or $repoTag -like "$prefix`:*") {
                try {
                    $parsedDate = [DateTime]::Parse($createdAt)
                    $images += [PSCustomObject]@{
                        Repository = $repoTag
                        ImageId = $imageId
                        CreatedAt = $parsedDate
                    }
                }
                catch {
                    # If date parsing fails, assign a very old date
                    $images += [PSCustomObject]@{
                        Repository = $repoTag
                        ImageId = $imageId
                        CreatedAt = [DateTime]::Parse("1970-01-01")
                    }
                }
            }
        }
    }
    
    # Sort by creation date (newest first)
    $images = $images | Sort-Object CreatedAt -Descending
    
    if ($images.Count -gt $MaxImages) {
        $imagesToDelete = $images | Select-Object -Skip $MaxImages
        
        Write-Host "Found $($images.Count) images for $prefix. Keeping $MaxImages newest, removing $($imagesToDelete.Count) old images." -ForegroundColor Cyan
        
        foreach ($image in $imagesToDelete) {
            try {
                Write-Host "Removing image: $($image.Repository) (ID: $($image.ImageId))" -ForegroundColor Red
                docker rmi $image.ImageId --force 2>$null
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "Successfully removed: $($image.Repository)" -ForegroundColor Green
                } else {
                    Write-Host "Could not remove: $($image.Repository) (might be in use)" -ForegroundColor Yellow
                }
            }
            catch {
                Write-Host "Error removing image $($image.Repository) : $($_.Exception.Message)" -ForegroundColor Red
            }
        }
    } else {
        Write-Host "Only $($images.Count) images found for $prefix. No cleanup needed." -ForegroundColor Green
    }
}

# Clean up dangling images
Write-Host "Cleaning up dangling images..." -ForegroundColor Yellow
docker image prune -f 2>$null

# Show remaining images
Write-Host "`nRemaining images:" -ForegroundColor Cyan
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.CreatedAt}}\t{{.Size}}" | Where-Object { 
    $line = $_
    $ImagePrefixes | Where-Object { $line -match $_ }
}

Write-Host "Docker image cleanup completed!" -ForegroundColor Green
