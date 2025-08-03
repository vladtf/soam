# SOAM: An Ontology-Driven Middleware Platform for Integrating Heterogeneous Data in Smart Cities


## Table of Contents

- [SOAM: An Ontology-Driven Middleware Platform for Integrating Heterogeneous Data in Smart Cities](#soam-an-ontology-driven-middleware-platform-for-integrating-heterogeneous-data-in-smart-cities)
  - [Table of Contents](#table-of-contents)
    - [Overview](#overview)
    - [Summary of Local Pages:](#summary-of-local-pages)
    - [Architecture Diagram](#architecture-diagram)
    - [Local Development](#local-development)
    - [Cloud Deployment](#cloud-deployment)
    - [Skaffold](#skaffold)

### Overview

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

- Start Mqtt Server:

```powershell
docker-compose up -d
```

- Start the backend:

```powershell
pipenv run uvicorn main:app --reload
```

- Start the frontend:

```powershell
npm run dev
```

### Cloud Deployment

### Skaffold

1. Create local registry:

```bash
docker run -d -p 5000:5000 --restart=always --name registry registry:2
```

2. Start Skaffold:

```bash
skaffold dev --default-repo localhost:5000
```