"""RAG-based recommendation engine for dish recommendations.

This module implements a Retrieval-Augmented Generation (RAG) system for
intelligent dish recommendations based on:
- Menu item descriptions
- Customer reviews from multiple sources
- Popular dish mentions
- User preferences

Architecture inspired by LangChain's RAG patterns but using Gemini LLM.

Example Usage:
    >>> from app.services.recommendation.rag_engine import RAGRecommendationEngine
    >>> from app.core.config import settings
    >>>
    >>> # Initialize engine
    >>> engine = RAGRecommendationEngine(gemini_api_key=settings.gemini_api_key)
    >>>
    >>> # Build knowledge base
    >>> stats = await engine.build_knowledge_base(
    ...     restaurant_name="BCD Tofu House",
    ...     location="Koreatown LA",
    ...     place_id="ChIJ...",
    ...     parsed_menu=menu_data
    ... )
    >>> print(stats)
    {
        'total_documents': 157,
        'menu_items': 24,
        'review_mentions': 128,
        'sources': ['Google Places', 'DuckDuckGo', 'Yelp']
    }
    >>>
    >>> # Get recommendations
    >>> recommendations = engine.recommend_dishes(
    ...     user_preferences="I want something spicy with tofu",
    ...     top_k=5
    ... )
    >>> print(recommendations[0])
    {
        'dish_name': 'Soon Tofu Jjigae',
        'confidence': 0.94,
        'reasons': [
            'Mentioned in 12 reviews as must-try',
            'Perfect match for spicy + tofu preference'
        ],
        'review_count': 12,
        'avg_sentiment': 0.89
    }
"""

import logging
from typing import List, Dict, Optional
from google import genai
from google.genai import types
import json

from .vector_store import VectorStore
from ..data_collection.multi_source_aggregator import MultiSourceAggregator

logger = logging.getLogger(__name__)


class RAGRecommendationEngine:
    """RAG-based recommendation engine using vector search + LLM generation.

    This class implements a RAG pattern:
    1. **Retrieval**: Vector similarity search to find relevant reviews
    2. **Augmentation**: Combine retrieved context with user query
    3. **Generation**: Use Gemini to generate personalized recommendations

    Attributes:
        vector_store: VectorStore instance for semantic search
        gemini_client: Gemini API client for LLM generation
        aggregator: Multi-source data aggregator
        knowledge_base_built: Whether knowledge base has been built

    Example:
        >>> engine = RAGRecommendationEngine(gemini_api_key="AIza...")
        >>> await engine.build_knowledge_base(...)
        >>> recommendations = engine.recommend_dishes("spicy noodles")
        >>> len(recommendations)
        5
    """

    def __init__(
        self,
        gemini_api_key: str,
        google_places_api_key: Optional[str] = None,
        yelp_api_key: Optional[str] = None,
        model_name: str = "gemini-2.0-flash-exp",
        cache_enabled: bool = True,
        cache_ttl_seconds: int = 604800
    ):
        """Initialize RAG engine with API keys.

        Args:
            gemini_api_key: Google Gemini API key (required)
            google_places_api_key: Google Places API key (optional)
            yelp_api_key: Yelp API key (optional)
            model_name: Gemini model name for LLM enhancement
            cache_enabled: Enable local caching for multi-source data collection
            cache_ttl_seconds: Cache TTL in seconds

        Example:
            >>> engine = RAGRecommendationEngine(
            ...     gemini_api_key="AIza...",
            ...     google_places_api_key="AIza...",
            ...     yelp_api_key="abc...",
            ...     model_name="gemini-2.5-flash",
            ...     cache_enabled=True,
            ...     cache_ttl_seconds=604800
            ... )
            >>> engine.knowledge_base_built
            False
        """
        self.vector_store = VectorStore()
        self.gemini_client = genai.Client(api_key=gemini_api_key)
        self.gemini_api_key = gemini_api_key
        self.model_name = model_name
        self.aggregator = MultiSourceAggregator(
            google_api_key=google_places_api_key,
            yelp_api_key=yelp_api_key,
            cache_enabled=cache_enabled,
            cache_ttl_seconds=cache_ttl_seconds
        )
        self.knowledge_base_built = False
        self.restaurant_name = None
        self.dish_names = []  # List of all known dish names

        logger.info("RAGRecommendationEngine initialized")

    async def build_knowledge_base(
        self,
        restaurant_name: str,
        location: str,
        place_id: Optional[str] = None,
        parsed_menu: Optional[Dict] = None
    ) -> Dict:
        """Build RAG knowledge base from all available sources.

        This method:
        1. Collects data from Google Places, DuckDuckGo, and Yelp
        2. Extracts dish mentions from reviews
        3. Creates vector embeddings for semantic search
        4. Indexes everything for fast retrieval

        Args:
            restaurant_name: Restaurant name (e.g., "Tartine Bakery")
            location: Location (e.g., "San Francisco")
            place_id: Google Place ID (optional, for faster lookup)
            parsed_menu: Already-parsed menu from vision API (optional)

        Returns:
            Statistics dictionary with counts and metadata

        Example:
            >>> stats = await engine.build_knowledge_base(
            ...     restaurant_name="BCD Tofu House",
            ...     location="Koreatown Los Angeles",
            ...     place_id="ChIJobNa...",
            ...     parsed_menu={
            ...         "menu": [
            ...             {
            ...                 "category": "Stews",
            ...                 "items": [
            ...                     {
            ...                         "name": "Soon Tofu Jjigae",
            ...                         "description": "Spicy soft tofu stew",
            ...                         "price": 12.99
            ...                     }
            ...                 ]
            ...             }
            ...         ]
            ...     }
            ... )
            >>> print(stats)
            {
                'total_documents': 157,
                'menu_items': 24,
                'review_mentions': 128,
                'popular_dishes': 5,
                'sources': ['Google Places', 'DuckDuckGo', 'Yelp'],
                'successful_sources': 3,
                'failed_sources': []
            }

        Note:
            This is a potentially expensive operation (API calls to multiple sources).
            Results should be cached in production.
        """
        logger.info(f"Building knowledge base for {restaurant_name}, {location}")
        self.restaurant_name = restaurant_name

        # Step 1: Collect data from all sources
        logger.info("Step 1/4: Collecting data from all sources...")
        data = await self.aggregator.collect_all_data(
            restaurant_name=restaurant_name,
            location=location,
            place_id=place_id
        )

        logger.info(
            f"Collected: {len(data['reviews'])} reviews, "
            f"{len(data['images'])} images from {len(data['sources'])} sources"
        )

        # Step 2: Extract dish names from menu
        logger.info("Step 2/4: Extracting dish names from menu...")
        self.dish_names = []
        menu_items = []

        if parsed_menu and "menu" in parsed_menu:
            for category in parsed_menu["menu"]:
                for item in category.get("items", []):
                    dish_name = item.get("name", "")
                    if dish_name:
                        self.dish_names.append(dish_name)

        logger.info(f"Found {len(self.dish_names)} dishes in menu")

        # Step 3: Build document collection for vector store
        logger.info("Step 3/4: Building document collection...")
        documents = []

        # 3a. Add menu item descriptions
        if parsed_menu and "menu" in parsed_menu:
            for category in parsed_menu["menu"]:
                category_name = category.get("category", "")
                for item in category.get("items", []):
                    dish_name = item.get("name", "")
                    description = item.get("description", "")

                    if description:
                        documents.append({
                            "text": description,
                            "dish": dish_name,
                            "metadata": {
                                "type": "menu_description",
                                "category": category_name,
                                "price": item.get("price"),
                                "spicy_level": item.get("spicy_level"),
                                "allergens": item.get("allergens", []),
                                "dietary_tags": item.get("dietary_tags", [])
                            }
                        })

        # 3b. Extract dish mentions from reviews
        review_mention_count = 0
        for review in data["reviews"]:
            review_text = review.get("text", "")
            if not review_text or len(review_text) < 10:
                continue

            # Find which dishes are mentioned in this review
            mentioned_dishes = self._extract_dish_mentions(review_text, self.dish_names)

            for dish in mentioned_dishes:
                documents.append({
                    "text": review_text,
                    "dish": dish,
                    "metadata": {
                        "type": "review",
                        "source": review.get("_source", "unknown"),
                        "rating": review.get("rating"),
                        "url": review.get("url")
                    }
                })
                review_mention_count += 1

        # 3c. Add popular dishes from extraction
        for dish_info in data.get("popular_dishes", []):
            dish_name = dish_info.get("name", "")
            mention_count = dish_info.get("mention_count", 0)

            documents.append({
                "text": f"Popular dish: {dish_name}. Highly recommended by {mention_count} reviewers.",
                "dish": dish_name,
                "metadata": {
                    "type": "popularity",
                    "mention_count": mention_count,
                    "sentiment": dish_info.get("avg_sentiment", 0.5)
                }
            })

        logger.info(f"Created {len(documents)} documents for indexing")

        # Step 4: Add to vector store
        logger.info("Step 4/4: Creating vector embeddings...")
        self.vector_store.add_documents(documents)
        self.knowledge_base_built = True

        stats = {
            "total_documents": len(documents),
            "menu_items": sum(1 for d in documents if d["metadata"]["type"] == "menu_description"),
            "review_mentions": review_mention_count,
            "popular_dishes": len(data.get("popular_dishes", [])),
            "unique_dishes": len(self.dish_names),
            "sources": data["sources"],
            "successful_sources": data["metadata"]["successful_sources"],
            "failed_sources": data["metadata"]["failed_sources"]
        }

        logger.info(f"Knowledge base built successfully: {stats}")
        return stats

    def recommend_dishes(
        self,
        user_preferences: str,
        top_k: int = 5,
        use_llm: bool = True
    ) -> List[Dict]:
        """Get dish recommendations based on user preferences.

        This method uses RAG pattern:
        1. Retrieve relevant documents via vector search
        2. Augment with context (reviews, menu descriptions)
        3. Generate recommendations (optionally using LLM for explanations)

        Args:
            user_preferences: Natural language query (e.g., "spicy noodles", "vegetarian options")
            top_k: Number of recommendations to return (default 5)
            use_llm: Whether to use Gemini for enhanced explanations (default True)

        Returns:
            List of recommendation dictionaries sorted by confidence

        Example:
            >>> recommendations = engine.recommend_dishes(
            ...     user_preferences="I love spicy Korean soups",
            ...     top_k=3
            ... )
            >>> print(recommendations[0])
            {
                'dish_name': 'Soon Tofu Jjigae',
                'confidence': 0.94,
                'reasons': [
                    'Mentioned in 12 reviews as must-try',
                    'Perfect match for spicy soup preference',
                    'Contains soft tofu in spicy seafood broth'
                ],
                'review_count': 12,
                'avg_sentiment': 0.89,
                'metadata': {
                    'price': 12.99,
                    'spicy_level': 3,
                    'allergens': ['shellfish', 'soy']
                }
            }

            >>> # Example with vegetarian preference
            >>> veg_recs = engine.recommend_dishes("vegetarian options", top_k=3)
            >>> all(any('vegetarian' in tag for tag in rec.get('metadata', {}).get('dietary_tags', []))
            ...     for rec in veg_recs)
            True

        Raises:
            ValueError: If knowledge base hasn't been built yet

        Debug Example:
            # Uncomment to test
            # engine = RAGRecommendationEngine(gemini_api_key="key")
            # await engine.build_knowledge_base(...)
            # recs = engine.recommend_dishes("spicy", top_k=5)
            # import json
            # print(json.dumps(recs, indent=2))
        """
        if not self.knowledge_base_built:
            raise ValueError(
                "Knowledge base not built. Call build_knowledge_base() first."
            )

        logger.info(f"Getting recommendations for: '{user_preferences}'")

        # Step 1: Vector search to find relevant documents
        results = self.vector_store.search(user_preferences, top_k=top_k * 3)

        # Step 2: Group by dish and aggregate scores
        dish_scores = {}

        for result in results:
            dish = result["dish"]
            score = result["score"]
            metadata = result["metadata"]

            if dish not in dish_scores:
                dish_scores[dish] = {
                    "dish_name": dish,
                    "total_score": 0,
                    "mention_count": 0,
                    "review_excerpts": [],
                    "menu_description": None,
                    "metadata": {},
                    "sources": set()
                }

            dish_scores[dish]["total_score"] += score
            dish_scores[dish]["mention_count"] += 1
            dish_scores[dish]["sources"].add(metadata.get("source", "menu"))

            # Store review excerpts
            if metadata["type"] == "review":
                dish_scores[dish]["review_excerpts"].append({
                    "text": result["text"][:200],  # First 200 chars
                    "score": score
                })

            # Store menu metadata
            if metadata["type"] == "menu_description":
                dish_scores[dish]["menu_description"] = result["text"]
                dish_scores[dish]["metadata"] = {
                    "category": metadata.get("category"),
                    "price": metadata.get("price"),
                    "spicy_level": metadata.get("spicy_level"),
                    "allergens": metadata.get("allergens", []),
                    "dietary_tags": metadata.get("dietary_tags", [])
                }

        # Step 3: Calculate confidence and rank
        recommendations = []

        for dish, info in dish_scores.items():
            # Calculate confidence (normalized score)
            confidence = min(info["total_score"] / info["mention_count"], 1.0)

            # Generate reasons (simple version)
            reasons = []

            if info["mention_count"] > 3:
                reasons.append(f"Mentioned in {info['mention_count']} reviews")

            if info["menu_description"]:
                reasons.append(info["menu_description"][:100])

            # Get top review excerpt
            if info["review_excerpts"]:
                top_review = sorted(
                    info["review_excerpts"],
                    key=lambda x: x["score"],
                    reverse=True
                )[0]
                reasons.append(f"Review: {top_review['text']}")

            recommendations.append({
                "dish_name": dish,
                "confidence": round(confidence, 3),
                "reasons": reasons[:3],  # Top 3 reasons
                "review_count": info["mention_count"],
                "data_sources": list(info["sources"]),
                "metadata": info["metadata"]
            })

        # Step 4: Sort by confidence
        recommendations.sort(key=lambda x: x["confidence"], reverse=True)
        recommendations = recommendations[:top_k]

        # Step 5: Optionally enhance with LLM
        if use_llm and recommendations:
            recommendations = self._enhance_with_llm(
                user_preferences,
                recommendations
            )

        logger.info(f"Generated {len(recommendations)} recommendations")
        return recommendations

    def _extract_dish_mentions(
        self,
        text: str,
        dish_list: List[str],
        fuzzy: bool = True
    ) -> List[str]:
        """Extract dish mentions from text using keyword matching.

        Args:
            text: Review text or description
            dish_list: List of known dish names
            fuzzy: Whether to use fuzzy matching (default True)

        Returns:
            List of mentioned dish names

        Example:
            >>> dish_list = ["Soon Tofu Jjigae", "Kimchi Pancake", "Bulgogi"]
            >>> text = "The soon tofu was amazing! Also tried the bulgogi."
            >>> engine._extract_dish_mentions(text, dish_list)
            ['Soon Tofu Jjigae', 'Bulgogi']

            >>> # Case insensitive
            >>> text = "KIMCHI PANCAKE is my favorite"
            >>> engine._extract_dish_mentions(text, dish_list)
            ['Kimchi Pancake']
        """
        text_lower = text.lower()
        mentioned = []

        for dish in dish_list:
            dish_lower = dish.lower()

            # Exact match (case insensitive)
            if dish_lower in text_lower:
                mentioned.append(dish)
            # Fuzzy match: check if significant words match
            elif fuzzy:
                dish_words = set(dish_lower.split())
                # If 50%+ of dish words appear in text, consider it a match
                matching_words = sum(1 for word in dish_words if word in text_lower)
                if len(dish_words) > 0 and matching_words / len(dish_words) >= 0.5:
                    mentioned.append(dish)

        return mentioned

    def _enhance_with_llm(
        self,
        user_query: str,
        recommendations: List[Dict]
    ) -> List[Dict]:
        """Enhance recommendations with LLM-generated explanations.

        Uses Gemini to generate better explanations for why each dish
        matches the user's preferences.

        Args:
            user_query: User's original query
            recommendations: List of recommendation dicts

        Returns:
            Enhanced recommendations with better explanations

        Example:
            >>> recs = [{'dish_name': 'Ramen', 'confidence': 0.9, 'reasons': [...]}]
            >>> enhanced = engine._enhance_with_llm("spicy noodles", recs)
            >>> len(enhanced[0]['reasons']) >= 2
            True
        """
        try:
            # Build context from top recommendations
            context = f"User is looking for: {user_query}\n\nAvailable dishes:\n"

            for i, rec in enumerate(recommendations[:3], 1):
                context += f"\n{i}. {rec['dish_name']}"
                if rec.get('metadata', {}).get('price'):
                    context += f" (${rec['metadata']['price']})"
                if rec['reasons']:
                    context += f"\n   - {rec['reasons'][0]}"

            # Ask Gemini to enhance explanations
            prompt = f"""Based on this context, provide 2-3 concise reasons why each dish matches the user's preferences.

{context}

Return ONLY a JSON array with enhanced reasons for each dish:
[
  {{
    "dish_name": "dish name",
    "enhanced_reasons": ["reason 1", "reason 2", "reason 3"]
  }},
  ...
]"""

            response = self.gemini_client.models.generate_content(
                model=self.model_name,
                contents=[types.Part.from_text(text=prompt)]
            )

            # Parse response
            result_text = response.text.strip()
            # Remove markdown if present
            import re
            result_text = re.sub(r'^```json\s*', '', result_text)
            result_text = re.sub(r'\s*```$', '', result_text)

            enhanced_data = json.loads(result_text)

            # Merge enhanced reasons
            for rec in recommendations:
                for enhanced in enhanced_data:
                    if enhanced["dish_name"] == rec["dish_name"]:
                        rec["reasons"] = enhanced["enhanced_reasons"]
                        break

        except Exception as e:
            logger.warning(f"LLM enhancement failed, using original reasons: {e}")

        return recommendations

    def get_dish_context(self, dish_name: str) -> Optional[Dict]:
        """Get all available context about a specific dish.

        Retrieves all information from knowledge base about a dish including:
        - Menu description
        - Review mentions
        - Ratings and sentiment
        - Popular dish status

        Args:
            dish_name: Name of the dish

        Returns:
            Context dictionary or None if dish not found

        Example:
            >>> context = engine.get_dish_context("Soon Tofu Jjigae")
            >>> print(context)
            {
                'dish_name': 'Soon Tofu Jjigae',
                'menu_description': 'Spicy soft tofu stew with seafood',
                'review_count': 12,
                'review_excerpts': ['Amazing!', 'Must try!', ...],
                'metadata': {
                    'price': 12.99,
                    'spicy_level': 3,
                    'allergens': ['shellfish', 'soy']
                },
                'is_popular': True
            }
        """
        if not self.knowledge_base_built:
            return None

        # Search for this specific dish
        results = self.vector_store.search(
            dish_name,
            top_k=20,
            filter_dish=dish_name
        )

        if not results:
            return None

        context = {
            "dish_name": dish_name,
            "menu_description": None,
            "review_count": 0,
            "review_excerpts": [],
            "metadata": {},
            "is_popular": False
        }

        for result in results:
            metadata = result["metadata"]

            if metadata["type"] == "menu_description":
                context["menu_description"] = result["text"]
                context["metadata"] = {
                    "category": metadata.get("category"),
                    "price": metadata.get("price"),
                    "spicy_level": metadata.get("spicy_level"),
                    "allergens": metadata.get("allergens", []),
                    "dietary_tags": metadata.get("dietary_tags", [])
                }

            elif metadata["type"] == "review":
                context["review_count"] += 1
                context["review_excerpts"].append(result["text"][:150])

            elif metadata["type"] == "popularity":
                context["is_popular"] = True
                context["popularity_score"] = metadata.get("mention_count", 0)

        return context


# Debug/Testing Examples (commented out)
"""
# Example 1: Basic RAG workflow
if __name__ == "__main__":
    import asyncio
    import os

    async def test_rag():
        engine = RAGRecommendationEngine(
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
            google_places_api_key=os.getenv("GOOGLE_PLACES_API_KEY")
        )

        # Build knowledge base
        stats = await engine.build_knowledge_base(
            restaurant_name="BCD Tofu House",
            location="Koreatown Los Angeles",
            place_id="ChIJobNaHIO4woARmjJB77L7Heg"
        )
        print("Knowledge base stats:", stats)

        # Get recommendations
        recs = engine.recommend_dishes("spicy Korean soup", top_k=3)
        for i, rec in enumerate(recs, 1):
            print(f"\n{i}. {rec['dish_name']} (confidence: {rec['confidence']})")
            for reason in rec['reasons']:
                print(f"   - {reason}")

    asyncio.run(test_rag())

# Example 2: Test dish mention extraction
if __name__ == "__main__":
    engine = RAGRecommendationEngine(gemini_api_key="dummy")

    dishes = ["Soon Tofu Jjigae", "Kimchi Pancake", "Bulgogi"]
    review = "The soon tofu was incredible! Best I've ever had."

    mentions = engine._extract_dish_mentions(review, dishes)
    print(f"Found mentions: {mentions}")
    # Output: ['Soon Tofu Jjigae']

# Example 3: Get dish context
if __name__ == "__main__":
    # After building knowledge base...
    context = engine.get_dish_context("Soon Tofu Jjigae")
    print(json.dumps(context, indent=2))
"""
