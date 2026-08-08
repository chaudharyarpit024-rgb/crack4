# CRACK - Diet Tracking App

## Overview
Simple, lightweight mobile diet tracker. Snap a photo of your food, get AI-estimated calories/fat/carbs, and log it against your daily target.

## Tech
- **Frontend:** Expo Router (React Native), TypeScript
- **Backend:** FastAPI + MongoDB (Motor)
- **Auth:** JWT (email + password, bcrypt)
- **AI:** Gemini 3 Flash via Emergent Universal LLM key
- **Camera:** expo-camera + expo-image-manipulator

## Features
1. **Auth** — Signup / Login (email + password, JWT persisted via SecureStore)
2. **Onboarding** — Goal (Gain/Lose/Maintain) + weight (kg) + height (cm) + optional age/gender → Mifflin-St Jeor daily calorie target
3. **Home** — Calorie progress ring, deficit/on-track/overeaten status badge, today's meals list, delete entries
4. **Camera flow** — Scan food → Gemini analysis → verdict (good/ok/bad) + macros → "Eating it" / "Not eating it"
5. **Manual entry** — Food name + calories (lightweight fallback)
6. **Profile** — Update goal/weight/height (recalculates target), last 30-day track record

## Backend endpoints
- `POST /api/auth/signup` `{email, password, name?}` → `{token, user}`
- `POST /api/auth/login` `{email, password}` → `{token, user}`
- `GET  /api/auth/me` → user
- `PUT  /api/profile` `{goal?, weight_kg?, height_cm?, age?, gender?}` → user (recalculates daily_target)
- `POST /api/food/analyze` `{image_base64}` → `{food_name, calories, fat_g, carbs_g, protein_g, verdict, reason}`
- `POST /api/food/log` `{food_name, calories, fat_g?, carbs_g?, protein_g?, source}` → entry
- `GET  /api/food/today` → `{items[], total_calories}`
- `GET  /api/food/history?days=30` → `{items[], days[]}`
- `DELETE /api/food/{id}` → `{ok}`

## Screens
`/` splash → gate • `/login` • `/signup` • `/onboarding` • `/(tabs)` home + profile • `/camera` • `/analyze` • `/manual`
