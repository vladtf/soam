# SOAM: An Ontology-Driven Middleware Platform for Integrating Heterogeneous Data in Smart Cities


## Table of Contents

- [SOAM: An Ontology-Driven Middleware Platform for Integrating Heterogeneous Data in Smart Cities](#soam-an-ontology-driven-middleware-platform-for-integrating-heterogeneous-data-in-smart-cities)
  - [Table of Contents](#table-of-contents)
    - [Overview](#overview)
    - [Summary of Local Pages:](#summary-of-local-pages)
    - [Local Development](#local-development)
    - [Cloud Deployment](#cloud-deployment)

### Overview

### Summary of Local Pages:

- **[Frontend](http://localhost:3000):** Accessible at `http://localhost:3000`
- **[Backend](http://localhost:8000):** Accessible at `http://localhost:8000`
- **[Spark Master UI](http://localhost:8080):** Accessible at `http://localhost:8080`
- **[Spark History Server UI](http://localhost:18080):** Accessible at `http://localhost:18080`
- **[MinIO S3 API](http://localhost:9000):** Accessible at `http://localhost:9000`
- **[MinIO Web Console](http://localhost:9090):** Accessible at `http://localhost:9090`
- **[Neo4j Web UI](http://localhost:7474):** Accessible at `http://localhost:7474`


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

