from ddgs import DDGS

def retrieve_reviews_and_images(query):
    text_results = DDGS().text(f"{query} reviews site:yelp.com OR site:tripadvisor.com", max_results=15)
    image_results = DDGS().images(query, max_results=3)

    return {
        "text_snippets": [
            {"title": r["title"], "snippet": r["body"], "url": r["href"]}
            for r in text_results
        ],
        "image_thumbnails": [
            {"title": img["title"], "image": img["image"], "source": img["source"]}
            for img in image_results
        ]
    }

query = "BCD Tofu House Koreatown best dishes recommendations"
results = retrieve_reviews_and_images(query)
# results = DDGS().text("BCD Tofu House Koreatown reviews", max_results=20)

for snippet in results["text_snippets"]:
    print(f"Title: {snippet['title']}\nSnippet: {snippet['snippet']}\nURL: {snippet['url']}\n")

for thumbnail in results["image_thumbnails"]:
    print(f"Title: {thumbnail['title']}\nImage URL: {thumbnail['image']}\nSource: {thumbnail['source']}\n")
# Example usage:
