#!/bin/bash

# Start Menu AI app locally without Docker
# This script requires two terminals - run backend and frontend separately

echo "=========================================="
echo "Menu AI - Local Development Setup"
echo "=========================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    echo "   Run: cp .env.example .env"
    echo "   Then add your GEMINI_API_KEY"
    exit 1
fi

# Check if GEMINI_API_KEY is set
source .env
if [ -z "$GEMINI_API_KEY" ]; then
    echo "❌ Error: GEMINI_API_KEY not set in .env"
    exit 1
fi

echo "✅ Environment configured"
echo ""
echo "Choose what to start:"
echo "  1) Backend only (port 8000)"
echo "  2) Frontend only (port 3000)"
echo ""
read -p "Enter choice (1 or 2): " choice

case $choice in
    1)
        echo ""
        echo "Starting Backend..."
        echo "=========================================="
        cd backend

        # Check if dependencies are installed
        if ! command -v uvicorn &> /dev/null; then
            echo "Installing backend dependencies..."
            uv pip install --system -r pyproject.toml
        fi

        echo ""
        echo "Backend running at: http://localhost:8000"
        echo "API Docs at: http://localhost:8000/docs"
        echo "Press Ctrl+C to stop"
        echo ""

        uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
        ;;
    2)
        echo ""
        echo "Starting Frontend..."
        echo "=========================================="
        cd frontend

        # Check if node_modules exists
        if [ ! -d "node_modules" ]; then
            echo "Installing frontend dependencies..."
            npm install
        fi

        echo ""
        echo "Frontend will run at: http://localhost:3000"
        echo "Make sure backend is running on port 8000"
        echo "Press Ctrl+C to stop"
        echo ""

        npm run dev
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac
