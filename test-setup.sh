#!/bin/bash

echo "========================================"
echo "Menu AI - Setup Verification"
echo "========================================"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    echo "   Please copy .env.example to .env and add your API key"
    exit 1
fi

# Check if GEMINI_API_KEY is set
if grep -q "your_api_key_here" .env; then
    echo "❌ Error: GEMINI_API_KEY not configured in .env"
    echo "   Please replace 'your_api_key_here' with your actual API key"
    exit 1
fi

echo "✅ Environment file configured"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running"
    echo "   Please start Docker Desktop"
    exit 1
fi

echo "✅ Docker is running"

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Error: docker-compose not found"
    echo "   Please install Docker Compose"
    exit 1
fi

echo "✅ Docker Compose is available"

# Check if menu_example.png exists
if [ -f menu_example.png ]; then
    echo "✅ Sample menu image found"
else
    echo "⚠️  Warning: menu_example.png not found (optional)"
fi

echo ""
echo "========================================"
echo "Setup verified! Ready to start."
echo "========================================"
echo ""
echo "To start the application:"
echo "  docker-compose up"
echo ""
echo "Then visit:"
echo "  Frontend: http://localhost:3000"
echo "  Backend:  http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
echo ""
