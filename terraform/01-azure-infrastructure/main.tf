# =============================================================================
# SOAM Infrastructure - Step 1: Azure Resources (AKS + ACR)
# =============================================================================
# This step creates the core Azure infrastructure:
# - Resource Group
# - Azure Container Registry (ACR)
# - Azure Kubernetes Service (AKS)
# - AKS-ACR role assignment
#
# After this step completes:
# 1. Build and push Docker images to ACR
# 2. Run Step 2 to deploy Kubernetes resources
# =============================================================================

terraform {
  required_version = ">= 1.0.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }

  # Backend configured via -backend-config in CI/CD
  # Uses Azure Storage for remote state
  backend "azurerm" {}
}

# =============================================================================
# Provider Configuration
# =============================================================================

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

# =============================================================================
# Variables
# =============================================================================

variable "subscription_id" {
  description = "Azure subscription ID"
  type        = string
}

variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
  default     = "soam-rg"
}

variable "location" {
  description = "Azure region for all resources"
  type        = string
  default     = "West Europe"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default = {
    project     = "soam"
    environment = "production"
    managed_by  = "terraform"
  }
}

variable "acr_name" {
  description = "Name of the Azure Container Registry (must be globally unique, alphanumeric only)"
  type        = string
  default     = "soamregistry"
}

variable "acr_sku" {
  description = "SKU for the Azure Container Registry (Basic, Standard, Premium)"
  type        = string
  default     = "Basic"
}

variable "aks_cluster_name" {
  description = "Name of the AKS cluster"
  type        = string
  default     = "soam-aks-cluster"
}

variable "aks_dns_prefix" {
  description = "DNS prefix for the AKS cluster"
  type        = string
  default     = "soamaks"
}

variable "aks_vm_size" {
  description = "VM size for AKS node pool"
  type        = string
  default     = "Standard_DS2_v2"
}

variable "aks_node_count" {
  description = "Initial number of nodes in the AKS cluster"
  type        = number
  default     = 3
}

variable "aks_enable_auto_scaling" {
  description = "Enable auto-scaling for the AKS node pool"
  type        = bool
  default     = false
}

variable "aks_min_node_count" {
  description = "Minimum number of nodes when auto-scaling is enabled"
  type        = number
  default     = 2
}

variable "aks_max_node_count" {
  description = "Maximum number of nodes when auto-scaling is enabled"
  type        = number
  default     = 5
}

# =============================================================================
# Resource Group
# =============================================================================

resource "azurerm_resource_group" "rg" {
  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}

# =============================================================================
# Azure Container Registry (ACR)
# =============================================================================

resource "azurerm_container_registry" "acr" {
  name                = var.acr_name
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = var.acr_sku
  admin_enabled       = true
  tags                = var.tags
}

# =============================================================================
# Azure Kubernetes Service (AKS)
# =============================================================================

resource "azurerm_kubernetes_cluster" "aks" {
  name                = var.aks_cluster_name
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  dns_prefix          = var.aks_dns_prefix

  default_node_pool {
    name                = "default"
    node_count          = var.aks_node_count
    vm_size             = var.aks_vm_size
    enable_auto_scaling = var.aks_enable_auto_scaling
    min_count           = var.aks_enable_auto_scaling ? var.aks_min_node_count : null
    max_count           = var.aks_enable_auto_scaling ? var.aks_max_node_count : null
  }

  identity {
    type = "SystemAssigned"
  }

  network_profile {
    network_plugin    = "azure"
    load_balancer_sku = "standard"
  }

  tags = var.tags
}

# Grant AKS permission to pull images from ACR
resource "azurerm_role_assignment" "aks_acr_pull" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_kubernetes_cluster.aks.kubelet_identity[0].object_id
}

# =============================================================================
# Outputs - Used by Step 2 and deployment script
# =============================================================================

output "resource_group_name" {
  description = "Name of the Azure resource group"
  value       = azurerm_resource_group.rg.name
}

output "acr_login_server" {
  description = "ACR login server URL for pushing images"
  value       = azurerm_container_registry.acr.login_server
}

output "acr_name" {
  description = "ACR name for login command"
  value       = azurerm_container_registry.acr.name
}

output "aks_cluster_name" {
  description = "Name of the AKS cluster"
  value       = azurerm_kubernetes_cluster.aks.name
}

output "aks_host" {
  description = "AKS API server host"
  value       = azurerm_kubernetes_cluster.aks.kube_config[0].host
  sensitive   = true
}

output "aks_client_certificate" {
  description = "AKS client certificate (base64)"
  value       = azurerm_kubernetes_cluster.aks.kube_config[0].client_certificate
  sensitive   = true
}

output "aks_client_key" {
  description = "AKS client key (base64)"
  value       = azurerm_kubernetes_cluster.aks.kube_config[0].client_key
  sensitive   = true
}

output "aks_cluster_ca_certificate" {
  description = "AKS cluster CA certificate (base64)"
  value       = azurerm_kubernetes_cluster.aks.kube_config[0].cluster_ca_certificate
  sensitive   = true
}

output "kube_config" {
  description = "Kubernetes configuration for kubectl"
  value       = azurerm_kubernetes_cluster.aks.kube_config_raw
  sensitive   = true
}

output "kube_config_command" {
  description = "Command to configure kubectl for the AKS cluster"
  value       = "az aks get-credentials --resource-group ${azurerm_resource_group.rg.name} --name ${azurerm_kubernetes_cluster.aks.name}"
}

output "docker_login_command" {
  description = "Command to login to ACR"
  value       = "az acr login --name ${azurerm_container_registry.acr.name}"
}
