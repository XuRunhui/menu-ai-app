# Contributing to Menu AI

Thank you for your interest in contributing to Menu AI! This document provides guidelines for contributing to the project.

## Development Setup

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/menu-ai-app.git
   cd menu-ai-app
   ```

3. Set up your environment:
   ```bash
   cp .env.example .env
   # Add your GEMINI_API_KEY to .env
   ```

4. Choose your development method:
   - **With Docker**: `docker-compose up`
   - **Without Docker**: See [GETTING_STARTED.md](GETTING_STARTED.md)

## Code Style

### Python (Backend)

- Follow PEP 8 style guidelines
- Use type hints for all function parameters and return types
- Write docstrings in Google style format
- Keep functions focused and under 20 lines when possible
- Use `ruff` for linting and formatting

### TypeScript/React (Frontend)

- Use TypeScript for all new files
- Follow React best practices and hooks patterns
- Use functional components
- Keep components small and reusable
- Use meaningful variable names

## Project Structure

- **backend/**: FastAPI backend application
  - `app/main.py`: API endpoints
  - `app/models/`: Pydantic data models
  - `app/services/`: Business logic
  - `app/core/`: Configuration

- **frontend/**: Next.js frontend application
  - `app/`: Next.js app directory (pages)
  - `components/`: Reusable React components
  - `lib/`: Utilities and API client

## Making Changes

1. Create a new branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes following the code style guidelines

3. Test your changes:
   - Backend: Run the backend and test the API endpoint
   - Frontend: Check the UI works as expected
   - Upload a test menu image to verify end-to-end functionality

4. Commit your changes:
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

   Use conventional commit messages:
   - `feat:` for new features
   - `fix:` for bug fixes
   - `docs:` for documentation changes
   - `style:` for formatting changes
   - `refactor:` for code refactoring
   - `test:` for adding tests

5. Push to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

6. Create a Pull Request on GitHub

## Pull Request Guidelines

- Provide a clear description of the changes
- Reference any related issues
- Include screenshots for UI changes
- Ensure all tests pass (if applicable)
- Update documentation as needed

## Areas for Contribution

Current roadmap includes:

**Phase 2**: Allergen Detection & Dietary Tags
- Add allergen detection (nuts, dairy, gluten, etc.)
- Implement dietary classification (vegan, vegetarian, gluten-free)
- Create visual badges in the UI

**Phase 3**: RAG for Recommendations
- Implement vector database integration
- Add dish recommendation system
- Create recommendation UI components

**Phase 4**: Web Scraping
- Add Yelp API integration
- Implement Google Maps scraping
- Create restaurant info display

## Questions?

Feel free to open an issue for:
- Bug reports
- Feature requests
- Questions about the codebase
- Suggestions for improvements

## Code of Conduct

Be respectful and constructive in all interactions. This project aims to create a welcoming environment for all contributors.
