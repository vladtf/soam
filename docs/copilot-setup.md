# 🤖 SOAM AI Copilot Setup Guide

SOAM includes an AI-powered Copilot feature that helps users generate computations using natural language. The Copilot analyzes your data sources and generates SQL-like computations based on your requirements.

## Prerequisites

1. **Azure OpenAI Service**: You need an Azure OpenAI resource with GPT-4 model deployed
2. **API Access**: Valid API key and endpoint from your Azure OpenAI service

## Azure OpenAI Setup

### 1. Create Azure OpenAI Resource

- Go to [Azure Portal](https://portal.azure.com)
- Create a new "Azure OpenAI" resource
- Choose your region and pricing tier
- Wait for deployment to complete

### 2. Deploy GPT-4 Model

- In your Azure OpenAI resource, go to "Model deployments"
- Click "Create new deployment"
- Select **GPT-4** model (recommended: `gpt-4` or `gpt-4-32k`)
- Choose deployment name (e.g., `gpt-4`)
- Set capacity as needed (start with 10K tokens per minute)

### 3. Get Credentials

- In Azure OpenAI resource, go to "Keys and Endpoint"
- Copy the **Endpoint** URL
- Copy one of the **API Keys**

## Environment Configuration

### Backend Configuration

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

### For Docker/Kubernetes

Update your deployment configuration:
```yaml
# In k8s/backend.yaml or docker-compose.yml
env:
  - name: AZURE_OPENAI_ENDPOINT
    value: "https://your-resource.openai.azure.com/"
  - name: AZURE_OPENAI_KEY
    value: "your-api-key-here"
```

## Testing the Setup

### Install Dependencies
```bash
cd backend/
pipenv install  # openai package already included
```

### Quick Setup (Recommended)
```bash
# Linux/Mac
chmod +x setup-copilot.sh && ./setup-copilot.sh

# Windows PowerShell
.\setup-copilot.ps1
```

### Manual Test
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

## Using the Copilot

### 1. Start the Application
```bash
# With Skaffold
skaffold dev --trigger=polling --watch-poll-interval=5000 --default-repo=localhost:5000/soam

# Or with Docker Compose
docker-compose up -d
```

### 2. Access the Frontend
- Navigate to [http://localhost:3000](http://localhost:3000)
- Go to "Data Processing" → "Computations" section
- Click "Add New Computation"
- Look for the **🤖 Generate with Copilot** button

### 3. Generate Computations
- Click the Copilot button
- Describe what you want in natural language:
  - *"Show me the average temperature by sensor location"*
  - *"Find sensors with readings above normal thresholds"*
  - *"Get the top 5 sensors with highest values this week"*
- Review the generated computation and suggestions
- Click "Use This Computation" to apply

## Copilot Features

- **🧠 Intelligent Analysis**: Analyzes your actual data schemas and samples
- **📝 Natural Language**: Converts plain English to SQL-like computations
- **✅ Validation**: Automatically validates generated computations
- **📊 Context-Aware**: Understands your data sources (bronze, silver, enriched, gold, alerts)
- **💡 Explanations**: Provides step-by-step reasoning for each computation
- **🎯 Column Suggestions**: Recommends which columns to display in dashboards
- **📈 Confidence Scoring**: Shows confidence level for each suggestion

## Troubleshooting

### Copilot button not visible
- Check that environment variables are properly set
- Verify the backend logs for Azure OpenAI connection errors
- Test with `python test_copilot.py`

### "Azure OpenAI not configured" error
- Ensure `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_KEY` are set
- Restart the backend service after setting environment variables

### "Failed to generate computation" error
- Check Azure OpenAI service limits and quotas
- Verify the GPT-4 model is properly deployed
- Check backend logs for detailed error messages

### Rate limiting
- Azure OpenAI has rate limits per minute/hour
- Consider upgrading your Azure OpenAI tier if needed
- Implement request queuing if using heavily

## Cost Considerations

- **Pricing**: Azure OpenAI charges per token (input + output)
- **Typical Cost**: Each computation generation costs ~$0.01-0.05
- **Optimization**: The system uses temperature=0.3 for consistent, efficient results
- **Monitoring**: Monitor usage in Azure OpenAI portal