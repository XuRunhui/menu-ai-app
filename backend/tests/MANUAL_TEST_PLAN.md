# Manual Testing Checklist

## Prerequisites
- [ ] All API keys configured in `.env`
- [ ] Docker containers running
- [ ] Can access `http://localhost:8000/docs`

## Test 1: Build Knowledge Base
- [ ] Go to `/docs`
- [ ] Find `/api/v1/recommendation/build-knowledge-base`
- [ ] Input: BCD Tofu House, Koreatown LA
- [ ] Click Execute
- [ ] Verify: Returns 200 with stats
- [ ] Verify: total_documents > 50
- [ ] Verify: At least 2 sources succeeded

## Test 2: Get Recommendations
- [ ] Find `/api/v1/recommendation/recommend`
- [ ] Input: "spicy Korean soup"
- [ ] Click Execute
- [ ] Verify: Returns 5 recommendations
- [ ] Verify: Top result has confidence > 0.7
- [ ] Verify: Reasons are meaningful

## Test 3: Taste & Texture Prediction
- [ ] Find `/api/v1/recommendation/taste-texture`
- [ ] Input: Soon Tofu Jjigae, "Spicy soft tofu stew"
- [ ] Set include_reviews: true
- [ ] Verify: Round 2 confidence > Round 1
- [ ] Verify: Tastes include "spicy"

## Test 4: Enhanced Menu OCR
- [ ] Use `/api/v1/menu/parse`
- [ ] Upload menu with spicy symbols (3 peppers)
- [ ] Verify: spicy_level = 3
- [ ] Upload menu with allergen text
- [ ] Verify: allergens list populated

## Test 5: Error Handling
- [ ] Call `/recommend` without building KB first
- [ ] Verify: 404 or clear error message
- [ ] Call with invalid restaurant name
- [ ] Verify: Graceful error response
