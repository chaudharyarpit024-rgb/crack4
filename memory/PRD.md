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
3. **Home** — Trial banner (X days left), Calorie progress ring, **total protein (g) pill under the ring**, deficit/on-track/overeaten status badge, today's meals list with **per-item protein displayed**, delete entries
4. **Camera flow** — Scan food (in-app camera) OR pick from gallery → Gemini analysis → verdict (good/ok/bad) + macros → "Eating it" / "Not eating it"
5. **Manual entry** — Food name + calories (lightweight fallback, always free)
6. **Profile** — Update goal/weight/height (recalculates target), Manage subscription link, **Terms of Service + Privacy Policy links**, last 30-day track record
7. **Subscription** — Auto-provisioned 10-day free trial on signup. ₹39/month (paise: 3900) Razorpay autopay after trial with 12 cycles per subscription. AI camera analysis is gated when subscription expires (soft paywall — manual entry still works). Fully-implemented Razorpay flow: `POST /api/subscription/checkout` → hosted checkout page → `POST /api/subscription/callback` (HMAC-verified) → `POST /api/subscription/webhook` (raw-body HMAC verify, idempotent via event_id index). Trial remains active in the app until `trial_ends_at` passes, even after checkout begins.
8. **Legal** — `/terms` (Terms of Service) and `/privacy` (Privacy Policy) screens, linked from Signup, Subscribe, and Profile.

## Backend endpoints
- Auth: `POST /api/auth/signup`, `POST /api/auth/login`, `GET /api/auth/me`
- Profile: `PUT /api/profile`
- Food: `POST /api/food/analyze` (requires active subscription/trial), `POST /api/food/log`, `GET /api/food/today`, `GET /api/food/history?days=30`, `DELETE /api/food/{id}`
- Subscription: `GET /api/subscription/me`, `POST /api/subscription/checkout`, `GET /api/subscription/checkout-page?subscription_id=...` (HTML), `POST /api/subscription/callback` (form), `POST /api/subscription/webhook` (raw)

## Screens
`/` splash → gate • `/login` • `/signup` • `/onboarding` • `/(tabs)` home + profile • `/camera` (with gallery button) • `/analyze` • `/manual` • `/subscribe` • `/terms` • `/privacy`

## Razorpay (LIVE keys configured)
- `RAZORPAY_KEY_ID=rzp_test_TNKjZ4cPbJPYfp`
- `RAZORPAY_KEY_SECRET` set in backend/.env
- `RAZORPAY_PLAN_ID=plan_TNKpaaAmmoDt7u` (₹39/month, INR)
- `RAZORPAY_WEBHOOK_SECRET` still placeholder — status updates rely on callback + `GET /subscription/me` refresh until admin adds a webhook secret + wires the Razorpay webhook URL.
