terraform {
  required_version = ">= 1.0.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
  }
}

provider "azurerm" {
  features {}
}

# Create a resource group for our AKS cluster.
resource "azurerm_resource_group" "rg" {
  name     = "soam-rg"
  location = "West Europe"
}

# New: Create an Azure Container Registry.
resource "azurerm_container_registry" "acr" {
  name                = "soamregistry"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = "Basic"
  admin_enabled       = true
}

# Create an Azure Kubernetes Service (AKS) cluster.
resource "azurerm_kubernetes_cluster" "aks" {
  name                = "soam-aks-cluster"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  dns_prefix          = "soamakscluster"

  default_node_pool {
    name       = "default"
    node_count = 2
    vm_size    = "Standard_DS2_v2"
  }

  identity {
    type = "SystemAssigned"
  }

  network_profile {
    network_plugin = "azure"
  }
}

# New: Assign the AcrPull role to AKS managed identity for pulling images from ACR.
resource "azurerm_role_assignment" "aks_acr_pull" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_kubernetes_cluster.aks.kubelet_identity[0].object_id
}

# Configure the Kubernetes provider using the AKS cluster's credentials.
provider "kubernetes" {
  host                   = azurerm_kubernetes_cluster.aks.kube_config.0.host
  client_certificate     = base64decode(azurerm_kubernetes_cluster.aks.kube_config.0.client_certificate)
  client_key             = base64decode(azurerm_kubernetes_cluster.aks.kube_config.0.client_key)
  cluster_ca_certificate = base64decode(azurerm_kubernetes_cluster.aks.kube_config.0.cluster_ca_certificate)
}

# Kubernetes Deployment for Mosquitto
resource "kubernetes_deployment" "mosquitto" {
  metadata {
    name = "mosquitto"
    labels = {
      app = "mosquitto"
    }
  }
  spec {
    replicas = 1
    selector {
      match_labels = {
        app = "mosquitto"
      }
    }
    template {
      metadata {
        labels = {
          app = "mosquitto"
        }
      }
      spec {
        container {
          name  = "mosquitto"
          image = "${azurerm_container_registry.acr.login_server}/mosquitto:latest"  # updated image reference
          port {
            container_port = 1883
          }
          port {
            container_port = 9001
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "mosquitto" {
  metadata {
    name = "mosquitto"
  }
  spec {
    selector = {
      app = kubernetes_deployment.mosquitto.metadata[0].labels["app"]
    }
    port {
      name        = "mqtt"
      port        = 1883
      target_port = 1883
      protocol    = "TCP"
    }
    port {
      name        = "websocket"
      port        = 9001
      target_port = 9001
      protocol    = "TCP"
    }
    type = "LoadBalancer"
  }
}

# Kubernetes Deployment for Simulator
resource "kubernetes_deployment" "simulator" {
  metadata {
    name = "simulator"
    labels = {
      app = "simulator"
    }
  }
  spec {
    replicas = 1
    selector {
      match_labels = {
        app = "simulator"
      }
    }
    template {
      metadata {
        labels = {
          app = "simulator"
        }
      }
      spec {
        container {
          name  = "simulator"
          image = "${azurerm_container_registry.acr.login_server}/simulator:latest"  # updated image reference
          env {
            name  = "MQTT_BROKER"
            value = "mosquitto"
          }
          # No exposed port if not required.
        }
      }
    }
  }
}

# Kubernetes Deployment for Frontend
resource "kubernetes_deployment" "frontend" {
  metadata {
    name = "frontend"
    labels = {
      app = "frontend"
    }
  }
  spec {
    replicas = 1
    selector {
      match_labels = {
        app = "frontend"
      }
    }
    template {
      metadata {
        labels = {
          app = "frontend"
        }
      }
      spec {
        container {
          name  = "frontend"
          image = "${azurerm_container_registry.acr.login_server}/frontend:latest"  # updated image reference
          port {
            container_port = 3000
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "frontend" {
  metadata {
    name = "frontend"
  }
  spec {
    selector = {
      app = kubernetes_deployment.frontend.metadata[0].labels["app"]
    }
    port {
      port        = 3000
      target_port = 3000
      protocol    = "TCP"
    }
    type = "LoadBalancer"
  }
}

# Kubernetes Deployment for Backend
resource "kubernetes_deployment" "backend" {
  metadata {
    name = "backend"
    labels = {
      app = "backend"
    }
  }
  spec {
    replicas = 1
    selector {
      match_labels = {
        app = "backend"
      }
    }
    template {
      metadata {
        labels = {
          app = "backend"
        }
      }
      spec {
        container {
          name  = "backend"
          image = "${azurerm_container_registry.acr.login_server}/backend:latest"  # updated image reference
          port {
            container_port = 8000
          }

          env {
            name  = "MQTT_BROKER"
            value = "mosquitto"
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "backend" {
  metadata {
    name = "backend"
  }
  spec {
    selector = {
      app = kubernetes_deployment.backend.metadata[0].labels["app"]
    }
    port {
      port        = 8000
      target_port = 8000
      protocol    = "TCP"
    }
    type = "LoadBalancer"
  }
}
