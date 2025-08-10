# SOAM: An Ontology-Driven Middleware Platform for Integrating Heterogeneous Data in Smart Cities


## Table of Contents

- [SOAM: An Ontology-Driven Middleware Platform for Integrating Heterogeneous Data in Smart Cities](#soam-an-ontology-driven-middleware-platform-for-integrating-heterogeneous-data-in-smart-cities)
  - [Table of Contents](#table-of-contents)
    - [Overview](#overview)
    - [Project Structure](#project-structure)
    - [Summary of Local Pages:](#summary-of-local-pages)
    - [Architecture Diagram](#architecture-diagram)
    - [Local Development](#local-development)
      - [Docker compose](#docker-compose)
      - [Skaffold](#skaffold)

### Overview

SOAM is a smart-city data platform that ingests heterogeneous sensor streams, normalizes data against an ontology, and provides analytics and observability. It includes:

- Backend: FastAPI + PySpark + SQLAlchemy, with MinIO S3 integration, Neo4j, and structured logging
- Frontend: React + Vite + React-Bootstrap, for browsing data, rules, and health
- Streaming: MQTT ingestion, Spark batch/streaming jobs, Delta Lake storage on MinIO
- Monitoring: Prometheus + Grafana, cAdvisor

### Project Structure

```
soam/
├─ backend/                # FastAPI service with Spark helpers and DB models
│  ├─ Dockerfile
│  └─ src/
│     ├─ api/              # FastAPI routers (health, minio, feedback, normalization)
│     ├─ database/         # SQLAlchemy models and DB helpers
│     ├─ logging_config.py # JSON logging configuration
│     ├─ middleware.py     # Request ID middleware
│     ├─ neo4j/            # Neo4j routes/integration
│     ├─ spark/            # Spark utilities (cleaner, usage tracker, routes)
│     └─ main.py           # FastAPI app entrypoint
├─ frontend/               # React (Vite) app
│  ├─ Dockerfile
│  └─ src/
│     ├─ api/              # API client for backend endpoints
│     ├─ components/       # UI building blocks
│     ├─ pages/            # Main pages (Dashboard, Normalization Rules, etc.)
│     └─ context/          # React contexts (config, error)
├─ ingestor/               # MQTT ingestion service
├─ simulator/              # Test MQTT publisher
├─ grafana/                # Grafana setup and dashboards
├─ prometheus/             # Prometheus setup
├─ k8s/                    # Kubernetes manifests for core services
├─ spark/                  # Spark image and configs
├─ skaffold.yaml           # Skaffold config (build + deploy)
├─ docker-compose.yml      # Local Mosquitto for quick tests
└─ tests/                  # Test scripts/utilities
```

### Summary of Local Pages:

- **[Frontend](http://localhost:3000):** Accessible at `http://localhost:3000`
- **[Backend](http://localhost:8000):** Accessible at `http://localhost:8000`
- **[Spark Master UI](http://localhost:8080):** Accessible at `http://localhost:8080`
- **[MinIO S3 API](http://localhost:9000):** Accessible at `http://localhost:9000`
- **[MinIO Web Console](http://localhost:9090):** Accessible at `http://localhost:9090`
- **[Neo4j Web UI](http://localhost:7474):** Accessible at `http://localhost:7474`
- **[Cadvisor Web UI](http://localhost:8089/metrics):** Accessible at `http://localhost:8089/metrics`
- **[Prometheus Web UI](http://localhost:9091):** Accessible at `http://localhost:9091`
- **[Grafana Web UI](http://localhost:3001):** Accessible at `http://localhost:3001`

### Architecture Diagram

<div style="border: 2px solid black; padding: 10px; display: inline-block;">
    <img src="assets/architecture.png" alt="Architecture" width="100%"/>
</div>

### Local Development

#### Docker compose

> [!NOTE]
> Docker compose is used for local development with Docker. Ensure you have Docker installed and running.

```bash
docker-compose up -d
```

#### Skaffold

> [!NOTE]
> Skaffold is used for local development with Kubernetes. Ensure you have a local K8s cluster running (e.g., Minikube or Docker Desktop).

```bash
skaffold dev
```

or

```bash
skaffold dev --trigger=polling --watch-poll-interval=5000
```
