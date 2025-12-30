# Menu AI Backend

FastAPI backend for AI-powered menu parsing using Gemini Vision API.

## Setup

1. Copy environment variables:
   ```bash
   cp .env.example .env
   ```

2. Add your Gemini API key to `.env`:
   ```
   GEMINI_API_KEY=your_actual_api_key
   ```

## Running Locally

### With Docker Compose (Recommended)
From the project root:
```bash
docker-compose up backend
```

### Without Docker
```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv pip install -e .

# Run the server
uvicorn app.main:app --reload
```

## API Endpoints

### Health Check
```bash
curl http://localhost:8000/
```

### Parse Menu
```bash
curl -X POST http://localhost:8000/api/v1/menu/parse \
  -F "image=@/path/to/menu.jpg"
```

## Project Structure

```
app/
├── main.py              # FastAPI application entry point
├── core/
│   └── config.py        # Configuration and environment variables
├── models/
│   └── menu.py          # Pydantic data models
└── services/
    └── vision_parser.py # Gemini Vision API integration
```
