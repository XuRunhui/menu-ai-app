# Getting Started with Menu AI

Quick reference for running the Menu AI application.

## Prerequisites Check

```bash
# Check Python version (need 3.11+)
python3 --version

# Check Node.js (need 20+)
node --version

# Check if you have uv (optional, recommended)
uv --version

# Check if you have Docker (optional)
docker --version
```

## Method 1: Without Docker (Current Setup)

Since you don't have Docker installed, use this method:

### First Time Setup

```bash
# 1. Navigate to the app
cd /home/ruxu/langchain/menu-ai-app

# 2. Verify .env file has your API key
cat .env  # Should show GEMINI_API_KEY=AIza...

# 3. Install uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh
# Then restart your terminal
```

### Running the App

**Terminal 1 - Backend:**
```bash
cd /home/ruxu/langchain/menu-ai-app
./start-local.sh
# Choose option 1 (Backend)
```

**Terminal 2 - Frontend:**
```bash
cd /home/ruxu/langchain/menu-ai-app
./start-local.sh
# Choose option 2 (Frontend)
```

### Manual Commands (Alternative)

If the script doesn't work, run these commands directly:

**Terminal 1 - Backend:**
```bash
cd /home/ruxu/langchain/menu-ai-app/backend
uv pip install --system -r pyproject.toml
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd /home/ruxu/langchain/menu-ai-app/frontend
npm install
npm run dev
```

### Access the App

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Method 2: With Docker (When Available)

When you have Docker installed:

```bash
cd /home/ruxu/langchain/menu-ai-app
docker-compose up
```

That's it! Everything runs automatically.

## Testing the App

1. Open http://localhost:3000 in your browser
2. Click "Choose File" and select `sample-menu.png`
3. Click "Parse Menu"
4. You should see structured menu data with categories and items

## Common Issues

**"uv: command not found"**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# Restart terminal
```

**"GEMINI_API_KEY not set"**
```bash
# Edit .env file in menu-ai-app directory
nano .env
# Add: GEMINI_API_KEY=your_actual_key
```

**"Port 8000 already in use"**
```bash
# Find and kill the process
lsof -i :8000
kill -9 <PID>
```

**Backend can't find .env**
- The .env file should be in `/home/ruxu/langchain/menu-ai-app/.env` (app root)
- The backend automatically looks in the parent directory
- You can also set the environment variable directly: `export GEMINI_API_KEY=your_key`

## Next Steps

After confirming the app works:
- Phase 2 will add allergen detection
- Phase 3 will add RAG for dish recommendations
- Phase 4 will add web scraping for restaurant info

See [README.md](README.md) for complete documentation.
