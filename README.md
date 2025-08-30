# SOAM: An Ontology-Driven Middleware Platform for Integrating Heterogeneous Data in Smart Cities


## Table of Contents

- [SOAM: An Ontology-Driven Middleware Platform for Integrating Heterogeneous Data in Smart Cities](#soam-an-ontology-driven-middleware-platform-for-integrating-heterogeneous-data-in-smart-cities)
  - [Table of Contents](#table-of-contents)
    - [Overview](#overview)
    - [Project Structure](#project-structure)
    - [Summary of Local Pages:](#summary-of-local-pages)
    - [Architecture Diagram](#architecture-diagram)
    - [🤖 Copilot Setup (AI-Powered Computation Generation)](#-copilot-setup-ai-powered-computation-generation)
    - [Local Development](#local-development)
      - [Pre-requisites](#pre-requisites)
      - [Docker compose](#docker-compose)
      - [Skaffold](#skaffold)

### Overview

SOAM is a smart-city data platform that ingests heterogeneous sensor streams, normalizes data against an ontology, and provides analytics and observability. It includes:

- Backend: FastAPI + PySpark + SQLAlchemy, with MinIO S3 integration, Neo4j, and structured logging
- Frontend: React + Vite + React-Bootstrap, for browsing data, rules, and health
- Streaming: MQTT ingestion, Spark batch/streaming jobs, Delta Lake storage on MinIO
- Monitoring: Prometheus + Grafana, cAdvisor
- **🤖 AI Copilot: Azure OpenAI-powered computation generation using natural language**

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

#### Pre-requisites

- Start local registry for Skaffold:

```powershell
# Start a local Docker registry
docker run -d -p 5000:5000 --name registry registry:2

# Set Skaffold default repository
skaffold config set default-repo localhost:5000/soam
```

### 🤖 Copilot Setup (AI-Powered Computation Generation)

SOAM includes an AI-powered Copilot feature that helps users generate computations using natural language. The Copilot analyzes your data sources and generates SQL-like computations based on your requirements.

#### Prerequisites

1. **Azure OpenAI Service**: You need an Azure OpenAI resource with GPT-4 model deployed
2. **API Access**: Valid API key and endpoint from your Azure OpenAI service

#### Azure OpenAI Setup

1. **Create Azure OpenAI Resource:**
   - Go to [Azure Portal](https://portal.azure.com)
   - Create a new "Azure OpenAI" resource
   - Choose your region and pricing tier
   - Wait for deployment to complete

2. **Deploy GPT-4 Model:**
   - In your Azure OpenAI resource, go to "Model deployments"
   - Click "Create new deployment"
   - Select **GPT-4** model (recommended: `gpt-4` or `gpt-4-32k`)
   - Choose deployment name (e.g., `gpt-4`)
   - Set capacity as needed (start with 10K tokens per minute)

3. **Get Credentials:**
   - In Azure OpenAI resource, go to "Keys and Endpoint"
   - Copy the **Endpoint** URL
   - Copy one of the **API Keys**

#### Environment Configuration

1. **Backend Configuration:**
   
   Create or update your environment configuration:
   ```bash
   cd backend/
   cp .env.copilot.example .env.local
   ```

   Edit `.env.local` (or add to your existing environment file):
   ```bash
   # Azure OpenAI Configuration
   AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
   AZURE_OPENAI_KEY=your-32-character-api-key-here
   AZURE_OPENAI_API_VERSION=2024-02-15-preview
   ```

   **Example:**
   ```bash
   AZURE_OPENAI_ENDPOINT=https://soam-copilot.openai.azure.com/
   AZURE_OPENAI_KEY=1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p
   AZURE_OPENAI_API_VERSION=2024-02-15-preview
   ```

2. **For Docker/Kubernetes:**
   
   Update your deployment configuration:
   ```yaml
   # In k8s/backend.yaml or docker-compose.yml
   env:
     - name: AZURE_OPENAI_ENDPOINT
       value: "https://your-resource.openai.azure.com/"
     - name: AZURE_OPENAI_KEY
       value: "your-api-key-here"
   ```

#### Testing the Setup

1. **Install Dependencies:**
   ```bash
   cd backend/
   pipenv install  # openai package already included
   ```

2. **Quick Setup (Recommended):**
   ```bash
   # Linux/Mac
   chmod +x setup-copilot.sh && ./setup-copilot.sh
   
   # Windows PowerShell
   .\setup-copilot.ps1
   ```

3. **Manual Test:**
   ```bash
   pipenv shell
   python test_copilot.py
   ```

   Expected output:
   ```
   ✅ Azure OpenAI environment variables found
   Endpoint: https://your-resource.openai.azure.com/
   ✅ CopilotService initialized successfully
   🤖 Copilot integration is ready!
   ```

#### Using the Copilot

1. **Start the Application:**
   ```bash
   # With Skaffold
   skaffold dev --trigger=polling --watch-poll-interval=5000 --default-repo=localhost:5000/soam
   
   # Or with Docker Compose
   docker-compose up -d
   ```

2. **Access the Frontend:**
   - Navigate to [http://localhost:3000](http://localhost:3000)
   - Go to "Data Processing" → "Computations" section
   - Click "Add New Computation"
   - Look for the **🤖 Generate with Copilot** button

3. **Generate Computations:**
   - Click the Copilot button
   - Describe what you want in natural language:
     - *"Show me the average temperature by sensor location"*
     - *"Find sensors with readings above normal thresholds"*
     - *"Get the top 5 sensors with highest values this week"*
   - Review the generated computation and suggestions
   - Click "Use This Computation" to apply

#### Copilot Features

- **🧠 Intelligent Analysis**: Analyzes your actual data schemas and samples
- **📝 Natural Language**: Converts plain English to SQL-like computations
- **✅ Validation**: Automatically validates generated computations
- **📊 Context-Aware**: Understands your data sources (bronze, silver, enriched, gold, alerts)
- **💡 Explanations**: Provides step-by-step reasoning for each computation
- **🎯 Column Suggestions**: Recommends which columns to display in dashboards
- **📈 Confidence Scoring**: Shows confidence level for each suggestion

#### Troubleshooting

**Copilot button not visible:**
- Check that environment variables are properly set
- Verify the backend logs for Azure OpenAI connection errors
- Test with `python test_copilot.py`

**"Azure OpenAI not configured" error:**
- Ensure `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_KEY` are set
- Restart the backend service after setting environment variables

**"Failed to generate computation" error:**
- Check Azure OpenAI service limits and quotas
- Verify the GPT-4 model is properly deployed
- Check backend logs for detailed error messages

**Rate limiting:**
- Azure OpenAI has rate limits per minute/hour
- Consider upgrading your Azure OpenAI tier if needed
- Implement request queuing if using heavily

#### Cost Considerations

- **Pricing**: Azure OpenAI charges per token (input + output)
- **Typical Cost**: Each computation generation costs ~$0.01-0.05
- **Optimization**: The system uses temperature=0.3 for consistent, efficient results
- **Monitoring**: Monitor usage in Azure OpenAI portal

---

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
skaffold dev --trigger=polling --watch-poll-interval=5000 --default-repo=localhost:5000/soam
```
