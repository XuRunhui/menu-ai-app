# Menu AI - AI-Powered Menu Parser

A web application that uses Gemini Vision API to parse restaurant menu images into structured data with multilingual support and Yelp integration for restaurant insights.

## Features

### Phase 1: Multilingual Menu Parsing ✅
- Upload menu images in any language (JPEG, PNG, etc.)
- Automatic language detection (Japanese, Chinese, Korean, Spanish, etc.)
- AI-powered translation to 12+ languages
- Native price handling (八百円, 십오 원, etc.)
- Toggle between original and translated text
- Clean, responsive web interface
- Real-time parsing feedback

### Phase 1.5: Restaurant Data Collection ✅
- Search restaurants by name and location via Yelp API
- View restaurant details (rating, reviews, photos)
- AI-powered popular dish extraction from reviews
- Photo gallery from Yelp
- Integration with menu parsing for contextual insights

## Quick Start

### Prerequisites

**Option A - With Docker (Recommended):**
- Docker and Docker Compose
- Gemini API key ([Get one here](https://aistudio.google.com/app/apikey))
- Yelp Fusion API key ([Get one here](https://www.yelp.com/developers/v3/manage_app)) - Optional for Phase 1.5 features

**Option B - Without Docker:**
- Python 3.11+ with `uv` package manager
- Node.js 20+
- Gemini API key ([Get one here](https://aistudio.google.com/app/apikey))
- Yelp Fusion API key ([Get one here](https://www.yelp.com/developers/v3/manage_app)) - Optional for Phase 1.5 features

### Setup with Docker

1. Navigate to the Menu AI app directory:
   ```bash
   cd /home/ruxu/langchain/menu-ai-app
   ```

2. Create a `.env` file:
   ```bash
   cp .env.example .env
   ```

3. Add your API keys to `.env`:
   ```
   GEMINI_API_KEY=your_actual_gemini_api_key_here
   YELP_API_KEY=your_actual_yelp_api_key_here
   ```

   Note: The app will work without a Yelp API key, but Phase 1.5 restaurant features will be disabled.

4. Start the application:
   ```bash
   docker-compose up
   ```

5. Open your browser:
   - Frontend: [http://localhost:3000](http://localhost:3000)
   - Backend API: [http://localhost:8000](http://localhost:8000)
   - API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### Setup without Docker

1. Navigate to the Menu AI app directory:
   ```bash
   cd /home/ruxu/langchain/menu-ai-app
   ```

2. Create a `.env` file in the app root:
   ```bash
   cp .env.example .env
   ```

3. Add your API keys to `.env`:
   ```
   GEMINI_API_KEY=your_actual_gemini_api_key_here
   YELP_API_KEY=your_actual_yelp_api_key_here
   ```

   Note: The app will work without a Yelp API key, but Phase 1.5 restaurant features will be disabled.

4. **Start the Backend** (Terminal 1):
   ```bash
   cd backend

   # Install uv if not already installed
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Install dependencies
   uv pip install --system -r pyproject.toml

   # Start the backend server
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

   The backend will start on [http://localhost:8000](http://localhost:8000)

5. **Start the Frontend** (Terminal 2):
   ```bash
   cd frontend

   # Install dependencies
   npm install

   # Start the development server
   npm run dev
   ```

   The frontend will start on [http://localhost:3000](http://localhost:3000)

6. Open your browser to [http://localhost:3000](http://localhost:3000)

**Alternative - Using Helper Script:**

You can use the provided script to start backend or frontend individually:

```bash
# From menu-ai-app directory, run the script
./start-local.sh

# Then choose:
# 1) Backend only (port 8000)
# 2) Frontend only (port 3000)
```

Run the script in two separate terminals (once for backend, once for frontend).

### Testing

1. Navigate to [http://localhost:3000](http://localhost:3000)
2. Click "Choose File" and select a menu image
3. Click "Parse Menu"
4. View the structured results

You can use the sample menu at `sample-menu.png` for testing.

## Project Structure

```
menu-ai-app/
├── backend/               # FastAPI backend
│   ├── app/
│   │   ├── main.py        # API endpoints
│   │   ├── models/        # Pydantic models
│   │   └── services/      # Business logic
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/              # Next.js frontend
│   ├── app/
│   │   └── page.tsx       # Main upload page
│   ├── components/        # React components
│   ├── lib/               # API client & types
│   └── Dockerfile
├── docker-compose.yml     # Local development setup
├── sample-menu.png        # Sample menu for testing
└── README.md              # This file
```

## Development

### Running Individual Services

**Backend Only:**
```bash
cd backend

# First time setup
uv pip install --system -r pyproject.toml

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend Only:**
```bash
cd frontend

# First time setup
npm install

# Start server
npm run dev
```

### Adding Dependencies

**Backend:**
```bash
cd backend

# Add a new package
uv pip install package-name

# Update pyproject.toml manually with the new dependency
```

**Frontend:**
```bash
cd frontend
npm install package-name
```

### Environment Variables

The backend reads from `.env` in the `menu-ai-app` root directory. Make sure to set:
- `GEMINI_API_KEY`: Your Gemini API key (required)

## API Reference

### POST /api/v1/menu/parse

Parse a menu image into structured JSON.

**Request:**
- Method: POST
- Content-Type: multipart/form-data
- Body: `image` (file)

**Response:**
```json
{
  "menu": [
    {
      "category": "Appetizers",
      "items": [
        {
          "name": "French Fries",
          "price": 5.99,
          "description": "Crispy golden fries"
        }
      ]
    }
  ]
}
```

## Next Steps (Phase 2)

According to the plan, Phase 2 will add:
- Allergen detection
- Dietary tag classification (vegan, vegetarian, gluten-free)
- Visual badges in the UI

## Troubleshooting

**Backend won't start:**
- Check that `GEMINI_API_KEY` is set in `.env` file in the `menu-ai-app` root directory
- Verify the API key is valid at [Google AI Studio](https://aistudio.google.com/app/apikey)
- Make sure you're in the `backend` directory when running uvicorn
- Check if port 8000 is already in use: `lsof -i :8000` or `netstat -ano | grep 8000`

**Frontend can't connect to backend:**
- Ensure backend is running on port 8000 (check terminal output)
- With Docker: Check `NEXT_PUBLIC_API_URL` in docker-compose.yml
- Without Docker: The frontend defaults to `http://localhost:8000` which should work automatically
- Test backend directly: `curl http://localhost:8000/` should return `{"status":"ok"}`

**Parsing errors:**
- Ensure image is clear and readable
- Try a different menu image (use `sample-menu.png` for testing)
- With Docker: Check backend logs: `docker-compose logs backend`
- Without Docker: Check the terminal where uvicorn is running

**uv command not found:**
- Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Restart your terminal after installation
- Alternatively, use pip: `pip install -r pyproject.toml` (not recommended)

**npm command not found:**
- Install Node.js from [nodejs.org](https://nodejs.org/) or use nvm
- Verify installation: `node --version` and `npm --version`

**Port already in use:**
- Backend (8000): Kill existing process or change port in uvicorn command
- Frontend (3000): Next.js will automatically suggest port 3001 if 3000 is taken

## License

This project is part of the LangChain development workflow.
