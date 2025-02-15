# SOAM: An Ontology-Driven Middleware Platform for Integrating Heterogeneous Data in Smart Cities


## Table of Contents

- [SOAM: An Ontology-Driven Middleware Platform for Integrating Heterogeneous Data in Smart Cities](#soam-an-ontology-driven-middleware-platform-for-integrating-heterogeneous-data-in-smart-cities)
  - [Table of Contents](#table-of-contents)
    - [Overview](#overview)
    - [Local Development](#local-development)
    - [Cloud Deployment](#cloud-deployment)

### Overview

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

