"""A restaurant's menu, assembled from every place it can be found and labelled by source.

No single source has the whole menu, so none of them stops the search:

- ``website``   the restaurant's own site — often the full menu, sometimes stale, and sometimes
                not theirs any more (expired domains get bought by unrelated sites)
- ``reviews``   dishes named in the five reviews Google returns — a handful at best
- ``upload``    a photo the diner takes — the freshest source, and the fallback for the rest

Google's place photos were tried as a fourth source and dropped: they added 10 of 457 dishes across
nine restaurants, cost up to ten billed requests per restaurant view, and couldn't be cached.

The website is read by ``website.py``; ``merge.py`` combines everything into one menu where every
dish says where it was seen.
"""
