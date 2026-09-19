# Prebuilt knowledge database

`push.sh` copies `backend/.data/knowledge.db` here before uploading, and the Dockerfile copies it
into the image. This keeps image builds fast and independent of Wikidata/Gutenberg uptime.

If no database is present, `docker build` falls back to building it from the network
(`python -m app.knowledge.cli build`), which can be slow.

The `.db` file is git-ignored; rebuild it locally with:

    cd backend && python -m app.knowledge.cli build
