variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
  default     = "aks-rg"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "East US"
}

variable "aks_cluster_name" {
  description = "Name of the AKS cluster"
  type        = string
  default     = "my-aks-cluster"
}

variable "acr_login_server" {
  description = "ACR login server (e.g., myregistry.azurecr.io)"
  type        = string
  default     = "myregistry.azurecr.io"
}
