---
title: Menuist
emoji: 🍜
colorFrom: yellow
colorTo: red
sdk: docker
app_port: 7860
pinned: false
short_description: Parse any menu photo and get AI dish recommendations
---

# Menuist — AI dining guide

Upload a menu photo (or click **Try a sample menu**) to get a structured, translatable menu with
dish photos, taste/texture predictions, and review-based recommendations.

- **Menu understanding:** DeepSeek multimodal (`deepseek-flash`, non-thinking mode)
- **Restaurant search:** Google Places reviews + web snippets, embedded with `all-MiniLM-L6-v2` for RAG
- **Stack:** Next.js 16 frontend · FastAPI backend · single Docker container

Source code: see the GitHub repository linked from the author's profile.
