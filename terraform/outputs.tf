output "kube_config" {
  value = azurerm_kubernetes_cluster.aks.kube_config_raw
  sensitive = true
}

output "acr_login_server" {
  value = azurerm_container_registry.acr.login_server
}

output "aks_principal_id" {
  value = azurerm_kubernetes_cluster.aks.kubelet_identity[0].object_id
}

output "backend_load_balancer_ip" {
  value = kubernetes_service.backend.status[0].load_balancer[0].ingress[0].ip
}

output "frontend_load_balancer_ip" {
  value = "http://${kubernetes_service.frontend.status[0].load_balancer[0].ingress[0].ip}:3000"
}