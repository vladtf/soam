$resourceGroup = "soam-rg"
$clusterName = "soam-aks-cluster"

az aks get-credentials --resource-group $resourceGroup --name $clusterName

