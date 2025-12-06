# =============================================================================
# SOAM Infrastructure - Step 2: Kubernetes Resources
# =============================================================================
# This step deploys all Kubernetes resources to AKS:
# - Namespace, Secrets, PVCs
# - Data layer: Mosquitto, Neo4j, MinIO, Spark
# - Application layer: Ingestor, Backend, Frontend
# - Optional: Simulator, REST API Simulator, Monitoring
#
# Prerequisites:
# - Step 1 completed (AKS + ACR created)
# - Docker images pushed to ACR
# =============================================================================

terraform {
  required_version = ">= 1.0.0"
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.0"
    }
  }

  backend "local" {
    path = "terraform.tfstate"
  }
}

# =============================================================================
# Variables
# =============================================================================

variable "aks_host" {
  description = "AKS API server host (from step 1)"
  type        = string
  sensitive   = true
}

variable "aks_client_certificate" {
  description = "AKS client certificate base64 (from step 1)"
  type        = string
  sensitive   = true
}

variable "aks_client_key" {
  description = "AKS client key base64 (from step 1)"
  type        = string
  sensitive   = true
}

variable "aks_cluster_ca_certificate" {
  description = "AKS cluster CA certificate base64 (from step 1)"
  type        = string
  sensitive   = true
}

variable "acr_login_server" {
  description = "ACR login server URL (from step 1)"
  type        = string
}

variable "kubernetes_namespace" {
  description = "Kubernetes namespace for SOAM resources"
  type        = string
  default     = "soam"
}

# MinIO Configuration
variable "minio_root_user" {
  description = "MinIO root username"
  type        = string
  default     = "minio"
  sensitive   = true
}

variable "minio_root_password" {
  description = "MinIO root password (minimum 8 characters)"
  type        = string
  default     = "minio123"
  sensitive   = true
}

variable "minio_storage_size" {
  description = "Storage size for MinIO persistent volume"
  type        = string
  default     = "10Gi"
}

# Neo4j Configuration
variable "neo4j_password" {
  description = "Neo4j database password"
  type        = string
  default     = "verystrongpassword"
  sensitive   = true
}

# Spark Configuration
variable "spark_worker_count" {
  description = "Number of Spark worker nodes"
  type        = number
  default     = 2
}

# Application Replicas
variable "frontend_replicas" {
  description = "Number of frontend replicas"
  type        = number
  default     = 1
}

variable "ingestor_replicas" {
  description = "Number of ingestor replicas"
  type        = number
  default     = 1
}

# Optional Components
variable "deploy_simulator" {
  description = "Deploy the MQTT simulator for testing"
  type        = bool
  default     = true
}

variable "deploy_rest_api_simulator" {
  description = "Deploy the REST API simulator for testing"
  type        = bool
  default     = false
}

variable "deploy_monitoring" {
  description = "Deploy monitoring stack (Prometheus + Grafana)"
  type        = bool
  default     = false
}

variable "grafana_admin_password" {
  description = "Grafana admin password"
  type        = string
  default     = "admin"
  sensitive   = true
}

# Azure OpenAI Configuration (Optional)
variable "azure_openai_endpoint" {
  description = "Azure OpenAI endpoint URL (leave empty to disable AI Copilot)"
  type        = string
  default     = ""
}

variable "azure_openai_key" {
  description = "Azure OpenAI API key"
  type        = string
  default     = ""
  sensitive   = true
}

variable "azure_openai_api_version" {
  description = "Azure OpenAI API version"
  type        = string
  default     = "2024-02-15-preview"
}

# =============================================================================
# Provider Configuration
# =============================================================================

provider "kubernetes" {
  host                   = var.aks_host
  client_certificate     = base64decode(var.aks_client_certificate)
  client_key             = base64decode(var.aks_client_key)
  cluster_ca_certificate = base64decode(var.aks_cluster_ca_certificate)
}

provider "helm" {
  kubernetes {
    host                   = var.aks_host
    client_certificate     = base64decode(var.aks_client_certificate)
    client_key             = base64decode(var.aks_client_key)
    cluster_ca_certificate = base64decode(var.aks_cluster_ca_certificate)
  }
}

# =============================================================================
# Kubernetes Namespace
# =============================================================================

resource "kubernetes_namespace" "soam" {
  metadata {
    name = var.kubernetes_namespace
  }
}

# =============================================================================
# Kubernetes Secrets
# =============================================================================

resource "kubernetes_secret" "minio_secret" {
  metadata {
    name      = "minio-secret"
    namespace = kubernetes_namespace.soam.metadata[0].name
  }

  data = {
    "root-user"     = var.minio_root_user
    "root-password" = var.minio_root_password
  }

  type = "Opaque"
}

resource "kubernetes_secret" "neo4j_secret" {
  metadata {
    name      = "neo4j-secret"
    namespace = kubernetes_namespace.soam.metadata[0].name
  }

  data = {
    "password" = var.neo4j_password
  }

  type = "Opaque"
}

# =============================================================================
# Persistent Volume Claims
# =============================================================================

resource "kubernetes_persistent_volume_claim" "backend_db" {
  metadata {
    name      = "backend-db-pvc"
    namespace = kubernetes_namespace.soam.metadata[0].name
  }

  spec {
    access_modes = ["ReadWriteOnce"]
    resources {
      requests = {
        storage = "1Gi"
      }
    }
    storage_class_name = "managed-premium"
  }

  wait_until_bound = false  # Don't wait - storage class uses WaitForFirstConsumer
}

resource "kubernetes_persistent_volume_claim" "ingestor_db" {
  metadata {
    name      = "ingestor-db-pvc"
    namespace = kubernetes_namespace.soam.metadata[0].name
  }

  spec {
    access_modes = ["ReadWriteOnce"]
    resources {
      requests = {
        storage = "1Gi"
      }
    }
    storage_class_name = "managed-premium"
  }

  wait_until_bound = false  # Don't wait - storage class uses WaitForFirstConsumer
}

# =============================================================================
# Mosquitto MQTT Broker
# =============================================================================

resource "kubernetes_deployment" "mosquitto" {
  metadata {
    name      = "mosquitto"
    namespace = kubernetes_namespace.soam.metadata[0].name
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
          image = "${var.acr_login_server}/mosquitto:latest"

          port {
            container_port = 1883
          }

          port {
            container_port = 9001
          }

          resources {
            requests = {
              cpu    = "50m"
              memory = "64Mi"
            }
            limits = {
              cpu    = "200m"
              memory = "256Mi"
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "mosquitto" {
  metadata {
    name      = "mosquitto"
    namespace = kubernetes_namespace.soam.metadata[0].name
  }

  spec {
    selector = {
      app = "mosquitto"
    }

    port {
      name        = "mqtt"
      port        = 1883
      target_port = 1883
    }

    port {
      name        = "websocket"
      port        = 9001
      target_port = 9001
    }

    type = "ClusterIP"
  }
}

# =============================================================================
# Neo4j Graph Database
# =============================================================================

resource "kubernetes_deployment" "neo4j" {
  metadata {
    name      = "neo4j"
    namespace = kubernetes_namespace.soam.metadata[0].name
    labels = {
      app = "neo4j"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "neo4j"
      }
    }

    template {
      metadata {
        labels = {
          app = "neo4j"
        }
      }

      spec {
        container {
          name  = "neo4j"
          image = "neo4j:5.17.0"

          port {
            container_port = 7474
          }

          port {
            container_port = 7687
          }

          env {
            name  = "NEO4J_AUTH"
            value = "neo4j/${var.neo4j_password}"
          }

          env {
            name  = "NEO4J_PLUGINS"
            value = "[\"apoc\", \"graph-data-science\", \"n10s\"]"
          }

          env {
            name  = "NEO4J_server_config_strict__validation_enabled"
            value = "false"
          }

          resources {
            requests = {
              cpu    = "200m"
              memory = "512Mi"
            }
            limits = {
              cpu    = "1000m"
              memory = "2Gi"
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "neo4j" {
  metadata {
    name      = "neo4j"
    namespace = kubernetes_namespace.soam.metadata[0].name
  }

  spec {
    selector = {
      app = "neo4j"
    }

    port {
      name        = "http"
      port        = 7474
      target_port = 7474
    }

    port {
      name        = "bolt"
      port        = 7687
      target_port = 7687
    }

    type = "ClusterIP"
  }
}

# =============================================================================
# MinIO Object Storage
# =============================================================================

resource "kubernetes_stateful_set" "minio" {
  metadata {
    name      = "minio"
    namespace = kubernetes_namespace.soam.metadata[0].name
    labels = {
      app = "minio"
    }
  }

  spec {
    service_name = "minio-headless"
    replicas     = 1

    selector {
      match_labels = {
        app = "minio"
      }
    }

    template {
      metadata {
        labels = {
          app = "minio"
        }
      }

      spec {
        container {
          name  = "minio"
          image = "minio/minio:RELEASE.2025-04-22T22-12-26Z-cpuv1"

          args = ["server", "/data", "--console-address", ":9090"]

          env {
            name = "MINIO_ROOT_USER"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.minio_secret.metadata[0].name
                key  = "root-user"
              }
            }
          }

          env {
            name = "MINIO_ROOT_PASSWORD"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.minio_secret.metadata[0].name
                key  = "root-password"
              }
            }
          }

          env {
            name  = "MINIO_PROMETHEUS_AUTH_TYPE"
            value = "public"
          }

          port {
            container_port = 9000
            name           = "api"
          }

          port {
            container_port = 9090
            name           = "console"
          }

          volume_mount {
            name       = "data"
            mount_path = "/data"
          }

          resources {
            requests = {
              cpu    = "250m"
              memory = "512Mi"
            }
            limits = {
              cpu    = "1000m"
              memory = "2Gi"
            }
          }
        }
      }
    }

    volume_claim_template {
      metadata {
        name = "data"
      }

      spec {
        access_modes       = ["ReadWriteOnce"]
        storage_class_name = "managed-premium"

        resources {
          requests = {
            storage = var.minio_storage_size
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "minio_headless" {
  metadata {
    name      = "minio-headless"
    namespace = kubernetes_namespace.soam.metadata[0].name
  }

  spec {
    cluster_ip                  = "None"
    publish_not_ready_addresses = true

    selector = {
      app = "minio"
    }

    port {
      name        = "api"
      port        = 9000
      target_port = 9000
    }
  }
}

resource "kubernetes_service" "minio" {
  metadata {
    name      = "minio"
    namespace = kubernetes_namespace.soam.metadata[0].name
  }

  spec {
    selector = {
      app = "minio"
    }

    port {
      name        = "api"
      port        = 9000
      target_port = 9000
    }

    port {
      name        = "console"
      port        = 9090
      target_port = 9090
    }

    type = "ClusterIP"
  }
}

# =============================================================================
# Apache Spark (using Bitnami Helm Chart)
# =============================================================================

resource "helm_release" "spark" {
  name       = "soam-spark"
  repository = "https://charts.bitnami.com/bitnami"
  chart      = "spark"
  version    = "9.2.13"
  namespace  = kubernetes_namespace.soam.metadata[0].name

  set {
    name  = "master.extraEnvVars[0].name"
    value = "JAVA_TOOL_OPTIONS"
  }
  set {
    name  = "master.extraEnvVars[0].value"
    value = "-Duser.home=/tmp"
  }
  set {
    name  = "master.extraEnvVars[1].name"
    value = "HOME"
  }
  set {
    name  = "master.extraEnvVars[1].value"
    value = "/tmp"
  }
  set {
    name  = "master.extraEnvVars[2].name"
    value = "SPARK_MASTER_HOST"
  }
  set {
    name  = "master.extraEnvVars[2].value"
    value = "0.0.0.0"
  }
  set {
    name  = "master.extraEnvVars[3].name"
    value = "PYSPARK_PYTHON"
  }
  set {
    name  = "master.extraEnvVars[3].value"
    value = "/usr/bin/python3"
  }
  set {
    name  = "master.extraEnvVars[4].name"
    value = "PYSPARK_DRIVER_PYTHON"
  }
  set {
    name  = "master.extraEnvVars[4].value"
    value = "/usr/bin/python3"
  }
  set {
    name  = "master.resources.requests.cpu"
    value = "500m"
  }
  set {
    name  = "master.resources.requests.memory"
    value = "1Gi"
  }
  set {
    name  = "master.resources.limits.cpu"
    value = "1"
  }
  set {
    name  = "master.resources.limits.memory"
    value = "2Gi"
  }
  set {
    name  = "worker.replicaCount"
    value = tostring(var.spark_worker_count)
  }
  set {
    name  = "worker.extraEnvVars[0].name"
    value = "PYSPARK_PYTHON"
  }
  set {
    name  = "worker.extraEnvVars[0].value"
    value = "/usr/bin/python3"
  }
  set {
    name  = "worker.resources.requests.cpu"
    value = "500m"
  }
  set {
    name  = "worker.resources.requests.memory"
    value = "1Gi"
  }
  set {
    name  = "worker.resources.limits.cpu"
    value = "2"
  }
  set {
    name  = "worker.resources.limits.memory"
    value = "4Gi"
  }
  set {
    name  = "image.registry"
    value = var.acr_login_server
  }
  set {
    name  = "image.repository"
    value = "spark"
  }
  set {
    name  = "image.tag"
    value = "latest"
  }
  set {
    name  = "global.security.allowInsecureImages"
    value = "true"
  }
}

# =============================================================================
# Ingestor Service
# =============================================================================

resource "kubernetes_deployment" "ingestor" {
  metadata {
    name      = "ingestor"
    namespace = kubernetes_namespace.soam.metadata[0].name
    labels = {
      app = "ingestor"
    }
  }

  spec {
    replicas = var.ingestor_replicas

    selector {
      match_labels = {
        app = "ingestor"
      }
    }

    template {
      metadata {
        labels = {
          app = "ingestor"
        }
      }

      spec {
        container {
          name  = "ingestor"
          image = "${var.acr_login_server}/ingestor:latest"

          port {
            container_port = 8001
          }

          env {
            name  = "MQTT_BROKER"
            value = "mosquitto"
          }

          env {
            name  = "MINIO_ENDPOINT"
            value = "minio:9000"
          }

          env {
            name  = "MINIO_ACCESS_KEY"
            value = var.minio_root_user
          }

          env {
            name  = "MINIO_SECRET_KEY"
            value = var.minio_root_password
          }

          volume_mount {
            name       = "ingestor-db"
            mount_path = "/data"
          }

          resources {
            requests = {
              cpu    = "100m"
              memory = "256Mi"
            }
            limits = {
              cpu    = "500m"
              memory = "512Mi"
            }
          }
        }

        volume {
          name = "ingestor-db"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim.ingestor_db.metadata[0].name
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "ingestor" {
  metadata {
    name      = "ingestor"
    namespace = kubernetes_namespace.soam.metadata[0].name
  }

  spec {
    selector = {
      app = "ingestor"
    }

    port {
      port        = 8001
      target_port = 8001
    }

    type = "ClusterIP"
  }
}

resource "kubernetes_service" "ingestor_external" {
  metadata {
    name      = "ingestor-external"
    namespace = kubernetes_namespace.soam.metadata[0].name
  }

  spec {
    selector = {
      app = "ingestor"
    }

    port {
      port        = 8001
      target_port = 8001
    }

    type = "LoadBalancer"
  }
}

# =============================================================================
# Backend Service
# =============================================================================

resource "kubernetes_stateful_set" "backend" {
  metadata {
    name      = "backend"
    namespace = kubernetes_namespace.soam.metadata[0].name
    labels = {
      app = "backend"
    }
  }

  spec {
    service_name = "backend"
    replicas     = 1

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
        init_container {
          name  = "wait-for-dependencies"
          image = "busybox:1.35"

          command = ["sh", "-c"]
          args = [
            <<-EOT
            echo "Waiting for Neo4j to be ready..."
            until nc -z neo4j 7474; do
              echo "Neo4j is not ready yet. Waiting 3 seconds..."
              sleep 3
            done
            echo "Neo4j is ready!"

            echo "Waiting for Spark Master to be ready..."
            until nc -z soam-spark-master-svc 7077; do
              echo "Spark Master is not ready yet. Waiting 5 seconds..."
              sleep 5
            done
            echo "Spark Master is ready!"
            EOT
          ]
        }

        container {
          name  = "backend"
          image = "${var.acr_login_server}/backend:latest"

          port {
            container_port = 8000
          }

          port {
            container_port = 41397
          }

          port {
            container_port = 41398
          }

          env {
            name  = "NEO4J_URI"
            value = "bolt://neo4j:7687"
          }

          env {
            name  = "NEO4J_USER"
            value = "neo4j"
          }

          env {
            name  = "NEO4J_PASSWORD"
            value = var.neo4j_password
          }

          env {
            name  = "SPARK_HOST"
            value = "soam-spark-master-svc"
          }

          env {
            name  = "SPARK_PORT"
            value = "7077"
          }

          env {
            name  = "SPARK_DRIVER_HOST"
            value = "backend-0.backend.${kubernetes_namespace.soam.metadata[0].name}.svc.cluster.local"
          }

          env {
            name  = "SPARK_UI_PORT"
            value = "80"
          }

          env {
            name  = "MINIO_ENDPOINT"
            value = "minio:9000"
          }

          env {
            name  = "MINIO_ACCESS_KEY"
            value = var.minio_root_user
          }

          env {
            name  = "MINIO_SECRET_KEY"
            value = var.minio_root_password
          }

          env {
            name  = "MINIO_BUCKET"
            value = "lake"
          }

          env {
            name  = "INGESTOR_BASE_URL"
            value = "http://ingestor:8001"
          }

          env {
            name  = "DATABASE_URL"
            value = "sqlite:////app/data/feedback.db"
          }

          env {
            name  = "SPARK_DRIVER_BIND_ADDRESS"
            value = "0.0.0.0"
          }

          env {
            name  = "SPARK_DRIVER_PORT"
            value = "41397"
          }

          env {
            name  = "SPARK_BLOCK_MANAGER_PORT"
            value = "41398"
          }

          env {
            name  = "PYTHONUNBUFFERED"
            value = "1"
          }

          env {
            name  = "LOG_LEVEL"
            value = "INFO"
          }

          # Azure OpenAI Configuration (optional)
          dynamic "env" {
            for_each = var.azure_openai_endpoint != "" ? [1] : []
            content {
              name  = "AZURE_OPENAI_ENDPOINT"
              value = var.azure_openai_endpoint
            }
          }

          dynamic "env" {
            for_each = var.azure_openai_key != "" ? [1] : []
            content {
              name  = "AZURE_OPENAI_KEY"
              value = var.azure_openai_key
            }
          }

          dynamic "env" {
            for_each = var.azure_openai_api_version != "" ? [1] : []
            content {
              name  = "AZURE_OPENAI_API_VERSION"
              value = var.azure_openai_api_version
            }
          }

          volume_mount {
            name       = "spark-events"
            mount_path = "/tmp/spark-events"
          }

          volume_mount {
            name       = "backend-db"
            mount_path = "/app/data"
          }

          resources {
            requests = {
              cpu    = "500m"
              memory = "512Mi"
            }
            limits = {
              cpu    = "2000m"
              memory = "2Gi"
            }
          }
        }

        volume {
          name = "spark-events"
          empty_dir {}
        }

        volume {
          name = "backend-db"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim.backend_db.metadata[0].name
          }
        }
      }
    }
  }

  depends_on = [
    kubernetes_deployment.neo4j,
    helm_release.spark
  ]
}

resource "kubernetes_service" "backend" {
  metadata {
    name      = "backend"
    namespace = kubernetes_namespace.soam.metadata[0].name
  }

  spec {
    cluster_ip = "None" # Headless service for StatefulSet

    selector = {
      app = "backend"
    }

    port {
      name        = "http"
      port        = 8000
      target_port = 8000
    }

    port {
      name        = "spark-driver"
      port        = 41397
      target_port = 41397
    }

    port {
      name        = "spark-block"
      port        = 41398
      target_port = 41398
    }
  }
}

# External service for LoadBalancer access (matches nginx.conf upstream name)
resource "kubernetes_service" "backend_external" {
  metadata {
    name      = "backend-external"
    namespace = kubernetes_namespace.soam.metadata[0].name
  }

  spec {
    selector = {
      app = "backend"
    }

    port {
      name        = "http"
      port        = 8000
      target_port = 8000
    }

    type = "LoadBalancer"
  }
}

resource "kubernetes_service" "backend_nodeport" {
  metadata {
    name      = "backend-nodeport"
    namespace = kubernetes_namespace.soam.metadata[0].name
  }

  spec {
    selector = {
      app = "backend"
    }

    port {
      name        = "http"
      port        = 8000
      target_port = 8000
    }

    type = "NodePort"
  }
}

# =============================================================================
# Frontend Service
# =============================================================================

resource "kubernetes_config_map" "frontend_config" {
  metadata {
    name      = "frontend-config"
    namespace = kubernetes_namespace.soam.metadata[0].name
  }

  data = {
    "config.json" = jsonencode({
      backendUrl  = "http://${kubernetes_service.backend_external.status[0].load_balancer[0].ingress[0].ip}:8000"
      ingestorUrl = "http://${kubernetes_service.ingestor_external.status[0].load_balancer[0].ingress[0].ip}:8001"
    })
  }

  depends_on = [
    kubernetes_service.backend_external,
    kubernetes_service.ingestor_external
  ]
}

resource "kubernetes_deployment" "frontend" {
  metadata {
    name      = "frontend"
    namespace = kubernetes_namespace.soam.metadata[0].name
    labels = {
      app = "frontend"
    }
  }

  spec {
    replicas = var.frontend_replicas

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
          image = "${var.acr_login_server}/frontend:latest"

          port {
            container_port = 80
          }

          volume_mount {
            name       = "frontend-config-volume"
            mount_path = "/usr/share/nginx/html/config"
            read_only  = true
          }

          resources {
            requests = {
              cpu    = "100m"
              memory = "128Mi"
            }
            limits = {
              cpu    = "500m"
              memory = "512Mi"
            }
          }
        }

        volume {
          name = "frontend-config-volume"
          config_map {
            name = kubernetes_config_map.frontend_config.metadata[0].name
          }
        }
      }
    }
  }

  depends_on = [kubernetes_config_map.frontend_config]
}

resource "kubernetes_service" "frontend" {
  metadata {
    name      = "frontend"
    namespace = kubernetes_namespace.soam.metadata[0].name
  }

  spec {
    selector = {
      app = "frontend"
    }

    port {
      port        = 80
      target_port = 80
    }

    type = "LoadBalancer"
  }
}

# =============================================================================
# Simulator (Optional)
# =============================================================================

resource "kubernetes_deployment" "simulator" {
  count = var.deploy_simulator ? 1 : 0

  metadata {
    name      = "simulator"
    namespace = kubernetes_namespace.soam.metadata[0].name
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
          image = "${var.acr_login_server}/simulator:latest"

          env {
            name  = "MQTT_BROKER"
            value = "mosquitto"
          }

          resources {
            requests = {
              cpu    = "50m"
              memory = "64Mi"
            }
            limits = {
              cpu    = "200m"
              memory = "256Mi"
            }
          }
        }
      }
    }
  }
}

# =============================================================================
# REST API Simulator (Optional)
# =============================================================================

resource "kubernetes_deployment" "rest_api_simulator" {
  count = var.deploy_rest_api_simulator ? 1 : 0

  metadata {
    name      = "rest-api-simulator"
    namespace = kubernetes_namespace.soam.metadata[0].name
    labels = {
      app = "rest-api-simulator"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "rest-api-simulator"
      }
    }

    template {
      metadata {
        labels = {
          app = "rest-api-simulator"
        }
      }

      spec {
        container {
          name  = "rest-api-simulator"
          image = "${var.acr_login_server}/rest-api-simulator:latest"

          port {
            container_port = 5000
          }

          resources {
            requests = {
              cpu    = "50m"
              memory = "64Mi"
            }
            limits = {
              cpu    = "200m"
              memory = "256Mi"
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "rest_api_simulator" {
  count = var.deploy_rest_api_simulator ? 1 : 0

  metadata {
    name      = "rest-api-simulator"
    namespace = kubernetes_namespace.soam.metadata[0].name
  }

  spec {
    selector = {
      app = "rest-api-simulator"
    }

    port {
      port        = 5000
      target_port = 5000
    }

    type = "ClusterIP"
  }
}

# =============================================================================
# Monitoring Stack (Optional)
# =============================================================================

resource "kubernetes_deployment" "prometheus" {
  count = var.deploy_monitoring ? 1 : 0

  metadata {
    name      = "prometheus"
    namespace = kubernetes_namespace.soam.metadata[0].name
    labels = {
      app = "prometheus"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "prometheus"
      }
    }

    template {
      metadata {
        labels = {
          app = "prometheus"
        }
      }

      spec {
        container {
          name  = "prometheus"
          image = "${var.acr_login_server}/prometheus:latest"

          args = ["--config.file=/etc/prometheus/prometheus.yml"]

          port {
            container_port = 9090
          }

          resources {
            requests = {
              cpu    = "100m"
              memory = "128Mi"
            }
            limits = {
              cpu    = "500m"
              memory = "512Mi"
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "prometheus" {
  count = var.deploy_monitoring ? 1 : 0

  metadata {
    name      = "prometheus"
    namespace = kubernetes_namespace.soam.metadata[0].name
  }

  spec {
    selector = {
      app = "prometheus"
    }

    port {
      port        = 9090
      target_port = 9090
    }

    type = "ClusterIP"
  }
}

resource "kubernetes_deployment" "grafana" {
  count = var.deploy_monitoring ? 1 : 0

  metadata {
    name      = "grafana"
    namespace = kubernetes_namespace.soam.metadata[0].name
    labels = {
      app = "grafana"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "grafana"
      }
    }

    template {
      metadata {
        labels = {
          app = "grafana"
        }
      }

      spec {
        container {
          name  = "grafana"
          image = "${var.acr_login_server}/grafana:latest"

          env {
            name  = "GF_SECURITY_ADMIN_USER"
            value = "admin"
          }

          env {
            name  = "GF_SECURITY_ADMIN_PASSWORD"
            value = var.grafana_admin_password
          }

          port {
            container_port = 3000
          }

          resources {
            requests = {
              cpu    = "100m"
              memory = "128Mi"
            }
            limits = {
              cpu    = "500m"
              memory = "512Mi"
            }
          }

          volume_mount {
            name       = "grafana-data"
            mount_path = "/var/lib/grafana"
          }
        }

        volume {
          name = "grafana-data"
          empty_dir {}
        }
      }
    }
  }
}

resource "kubernetes_service" "grafana" {
  count = var.deploy_monitoring ? 1 : 0

  metadata {
    name      = "grafana"
    namespace = kubernetes_namespace.soam.metadata[0].name
  }

  spec {
    selector = {
      app = "grafana"
    }

    port {
      port        = 3000
      target_port = 3000
    }

    type = "LoadBalancer"
  }
}

# =============================================================================
# Outputs
# =============================================================================

output "namespace" {
  description = "Kubernetes namespace"
  value       = kubernetes_namespace.soam.metadata[0].name
}

output "frontend_url" {
  description = "URL to access the SOAM frontend dashboard"
  value       = "http://${kubernetes_service.frontend.status[0].load_balancer[0].ingress[0].ip}"
}

output "backend_url" {
  description = "URL to access the SOAM backend API"
  value       = "http://${kubernetes_service.backend_external.status[0].load_balancer[0].ingress[0].ip}:8000"
}

output "backend_docs_url" {
  description = "URL to access the SOAM backend API documentation (Swagger UI)"
  value       = "http://${kubernetes_service.backend_external.status[0].load_balancer[0].ingress[0].ip}:8000/docs"
}

output "ingestor_url" {
  description = "URL to access the SOAM ingestor service"
  value       = "http://${kubernetes_service.ingestor_external.status[0].load_balancer[0].ingress[0].ip}:8001"
}

output "grafana_url" {
  description = "URL to access Grafana (if monitoring is enabled)"
  value       = var.deploy_monitoring ? "http://${kubernetes_service.grafana[0].status[0].load_balancer[0].ingress[0].ip}:3000" : "Monitoring not deployed"
}
