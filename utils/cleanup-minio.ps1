# MinIO PVC Cleanup Script
# Deletes MinIO PVCs to start fresh with empty storage

# Check if PVCs exist
$pvcs = kubectl get pvc -l app=minio --no-headers 2>$null
if ([string]::IsNullOrWhiteSpace($pvcs)) {
    Write-Host "No MinIO PVCs to clean up" -ForegroundColor Green
    exit 0
}

# Delete PVCs
Write-Host "Deleting MinIO PVCs..." -ForegroundColor Yellow
kubectl delete pvc -l app=minio --ignore-not-found=true
Write-Host "✅ MinIO cleanup done" -ForegroundColor Green
