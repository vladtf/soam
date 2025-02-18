# Variables
$registry = "soamregistry.azurecr.io"      # Replace with your container registry name
$projectName = "soam"               # Replace with your docker-compose project name (defaults to the folder name)
$services = @("simulator", "frontend", "backend", "mosquitto")

# Login to Azure Container Registry
Write-Host "Logging in to Azure Container Registry..."
az acr login --name $registry

# Build images using docker-compose
Write-Host "Building images using docker-compose..."
docker compose build
if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker Compose build failed! Exiting script."
    exit 1
}

# Loop over each service to tag and push images
foreach ($service in $services) {
    # Docker Compose by default names the image as <project>_<service>:latest
    $localImage = "$projectName" + "-" + "$service" + ":latest"
    $remoteImage = "$registry/$service"+":latest"
    
    Write-Host "Tagging image $localImage as $remoteImage..."
    docker tag $localImage $remoteImage
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Tagging failed for service $service. Exiting script."
        exit 1
    }
    
    Write-Host "Pushing image $remoteImage to registry..."
    docker push $remoteImage
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Push failed for service $service. Exiting script."
        exit 1
    }
}

Write-Host "All images built, tagged, and pushed successfully!" -ForegroundColor Green
