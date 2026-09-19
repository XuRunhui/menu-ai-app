"""Culinary knowledge base: documents + chunks for RAG, entities + edges for the food graph.

Lives in its own SQLite file (backend/.data/knowledge.db) because it is reference data that can be
rebuilt at any time with `python -m app.knowledge.cli build`, unlike user and cache data.
"""
