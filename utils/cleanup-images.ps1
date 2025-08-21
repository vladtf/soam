# Docker Image Cleanup Script
# This script removes old Docker images to prevent accumulation of too many tags locally
# It dynamically reads the Skaffold configuration to identify which images to clean up

param(
    [int]$MaxImages = 10,
    [string]$SkaffoldFile = "skaffold.yaml"
)

# Function to parse Skaffold YAML and extract image names
function Get-SkaffoldImages {
    param([string]$SkaffoldPath)
    
    $imageNames = @()
    
    if (-not (Test-Path $SkaffoldPath)) {
        Write-Warning "Skaffold file not found at: $SkaffoldPath"
        return @("mosquitto", "simulator", "frontend", "backend", "ingestor", "spark", "grafana", "prometheus")
    }
    
    try {
        Write-Host "Parsing Skaffold configuration from: $SkaffoldPath" -ForegroundColor Cyan
        
        # Try to use PowerShell-Yaml module if available
        if (Get-Module -ListAvailable -Name powershell-yaml) {
            Import-Module powershell-yaml -ErrorAction Stop
            $yamlContent = Get-Content $SkaffoldPath -Raw
            $config = ConvertFrom-Yaml $yamlContent
            
            if ($config.build -and $config.build.artifacts) {
                foreach ($artifact in $config.build.artifacts) {
                    if ($artifact.image) {
                        $imageNames += $artifact.image
                        Write-Host "  Found image: $($artifact.image)" -ForegroundColor Green
                    }
                }
            }
        }
        else {
            # Fallback: Install powershell-yaml module if not available
            Write-Host "Installing PowerShell-Yaml module..." -ForegroundColor Yellow
            try {
                Install-Module -Name powershell-yaml -Force -Scope CurrentUser -ErrorAction Stop
                Import-Module powershell-yaml -ErrorAction Stop
                
                $yamlContent = Get-Content $SkaffoldPath -Raw
                $config = ConvertFrom-Yaml $yamlContent
                
                if ($config.build -and $config.build.artifacts) {
                    foreach ($artifact in $config.build.artifacts) {
                        if ($artifact.image) {
                            $imageNames += $artifact.image
                            Write-Host "  Found image: $($artifact.image)" -ForegroundColor Green
                        }
                    }
                }
            }
            catch {
                Write-Warning "Could not install PowerShell-Yaml module. Falling back to regex parsing."
                return Get-SkaffoldImagesRegex -SkaffoldPath $SkaffoldPath
            }
        }
        
        if ($imageNames.Count -eq 0) {
            Write-Warning "No images found in Skaffold configuration. Using default list."
            return @("mosquitto", "simulator", "frontend", "backend", "ingestor", "spark", "grafana", "prometheus")
        }
        
        Write-Host "Successfully parsed $($imageNames.Count) images from Skaffold configuration" -ForegroundColor Green
        return $imageNames
    }
    catch {
        Write-Warning "Error parsing Skaffold file with YAML parser: $($_.Exception.Message). Using regex fallback."
        return Get-SkaffoldImagesRegex -SkaffoldPath $SkaffoldPath
    }
}

# Fallback function using regex parsing
function Get-SkaffoldImagesRegex {
    param([string]$SkaffoldPath)
    
    $imageNames = @()
    
    try {
        Write-Host "Using regex-based YAML parsing..." -ForegroundColor Yellow
        
        # Read the YAML content
        $content = Get-Content $SkaffoldPath -Raw
        
        # Simple regex-based YAML parsing for artifacts section
        # Look for lines like "- image: imagename" under the artifacts section
        $lines = $content -split "`n"
        $inArtifactsSection = $false
        
        foreach ($line in $lines) {
            $trimmedLine = $line.Trim()
            
            # Detect if we're in the artifacts section
            if ($trimmedLine -match "^artifacts:") {
                $inArtifactsSection = $true
                continue
            }
            
            # Stop when we reach a new top-level section
            if ($inArtifactsSection -and $trimmedLine -match "^[a-zA-Z].*:" -and -not $trimmedLine.StartsWith("- ")) {
                $inArtifactsSection = $false
                continue
            }
            
            # Extract image names from artifact entries
            if ($inArtifactsSection -and $trimmedLine -match "^\s*-\s*image:\s*(.+)$") {
                $imageName = $matches[1].Trim()
                # Remove quotes if present
                $imageName = $imageName -replace '^["\x27]|["\x27]$', ''
                $imageNames += $imageName
                Write-Host "  Found image: $imageName" -ForegroundColor Green
            }
        }
        
        if ($imageNames.Count -eq 0) {
            Write-Warning "No images found in Skaffold configuration. Using default list."
            return @("mosquitto", "simulator", "frontend", "backend", "ingestor", "spark", "grafana", "prometheus")
        }
        
        return $imageNames
    }
    catch {
        Write-Warning "Error parsing Skaffold file: $($_.Exception.Message). Using default list."
        return @("mosquitto", "simulator", "frontend", "backend", "ingestor", "spark", "grafana", "prometheus")
    }
}

# Get image prefixes from Skaffold configuration
$ImagePrefixes = Get-SkaffoldImages -SkaffoldPath $SkaffoldFile

Write-Host "Starting Docker image cleanup..." -ForegroundColor Green
Write-Host "Target images: $($ImagePrefixes -join ', ')" -ForegroundColor Cyan
Write-Host ""

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
