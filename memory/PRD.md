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
3. **Home** — Trial banner (X days left), Calorie progress ring, deficit/on-track/overeaten status badge, today's meals list, delete entries
4. **Camera flow** — Scan food (in-app camera) OR pick from gallery → Gemini analysis → verdict (good/ok/bad) + macros → "Eating it" / "Not eating it"
5. **Manual entry** — Food name + calories (lightweight fallback, always free)
6. **Profile** — Update goal/weight/height (recalculates target), Manage subscription link, last 30-day track record
7. **Subscription** — Auto-provisioned 10-day free trial on signup. ₹39/month (paise: 3900) Razorpay autopay after trial. AI camera analysis is gated when subscription expires (soft paywall — manual entry still works). Fully-implemented Razorpay flow: `POST /api/subscription/checkout` → hosted checkout page → `POST /api/subscription/callback` (HMAC-verified) → `POST /api/subscription/webhook` (raw-body HMAC verify, idempotent via event_id index).

## Backend endpoints
- Auth: `POST /api/auth/signup`, `POST /api/auth/login`, `GET /api/auth/me`
- Profile: `PUT /api/profile`
- Food: `POST /api/food/analyze` (requires active subscription/trial), `POST /api/food/log`, `GET /api/food/today`, `GET /api/food/history?days=30`, `DELETE /api/food/{id}`
- Subscription: `GET /api/subscription/me`, `POST /api/subscription/checkout`, `GET /api/subscription/checkout-page?subscription_id=...` (HTML), `POST /api/subscription/callback` (form), `POST /api/subscription/webhook` (raw)

## Screens
`/` splash → gate • `/login` • `/signup` • `/onboarding` • `/(tabs)` home + profile • `/camera` (with gallery button) • `/analyze` • `/manual` • `/subscribe`

## Setup for real payments
Add to `backend/.env` (replace placeholders):
- `RAZORPAY_KEY_ID` (rzp_test_... from dashboard.razorpay.com)
- `RAZORPAY_KEY_SECRET`
- `RAZORPAY_WEBHOOK_SECRET`
- `RAZORPAY_PLAN_ID` (create ₹39 monthly plan via `POST /v1/plans`, amount=3900, INR, period=monthly)
Configure webhook in Razorpay dashboard to `<PUBLIC_API_URL>/api/subscription/webhook` and subscribe to: `subscription.authenticated`, `subscription.activated`, `subscription.charged`, `subscription.pending`, `subscription.halted`, `subscription.cancelled`, `subscription.completed`.
