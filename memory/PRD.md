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
7. **Subscription** — Auto-provisioned 21. -day free trial on signup. ₹57/month (paise: 5700) Razorpay autopay after trial with 12 cycles per subscription. AI camera analysis is gated when subscription expires (soft paywall — manual entry still works). Fully-implemented Razorpay flow: `POST /api/subscription/checkout` → hosted checkout page → `POST /api/subscription/callback` (HMAC-verified) → `POST /api/subscription/webhook` (raw-body HMAC verify, idempotent via event_id index). Trial remains active in the app until `trial_ends_at` passes, even after checkout begins.
8. **Legal** — `/terms` (Terms of Service) and `/privacy` (Privacy Policy) screens, linked from Signup, Subscribe, and Profile.

## Backend endpoints
- Auth: `POST /api/auth/signup`, `POST /api/auth/login`, `GET /api/auth/me`
- Profile: `PUT /api/profile`
- Food: `POST /api/food/analyze` (requires active subscription/trial), `POST /api/food/log`, `GET /api/food/today`, `GET /api/food/history?days=30`, `DELETE /api/food/{id}`
- Subscription: `GET /api/subscription/me`, `POST /api/subscription/checkout`, `GET /api/subscription/checkout-page?subscription_id=...` (HTML), `POST /api/subscription/callback` (form), `POST /api/subscription/webhook` (raw)

## Screens
`/` splash → gate • `/login` • `/signup` • `/onboarding` • `/(tabs)` home + profile • `/camera` (with gallery button) • `/analyze` • `/manual` • `/subscribe` • `/terms` • `/privacy`


## Security posture (post-audit)
- **XSS-hardened** `/api/subscription/checkout-page` — subscription_id validated against `^sub_[A-Za-z0-9]{6,32}$`, DB-existence checked, JS output escaped and CSP + `X-Content-Type-Options: nosniff` set.
- **Strong secrets** — `JWT_SECRET` = 48-byte urlsafe random; boot fails on placeholder/<32 chars; JWT TTL reduced 30d → 7d.
- **Webhook fail-closed** — `/api/subscription/webhook` returns 503 if the secret is placeholder; forged signatures → 400; unique index on `rzp_events.event_id` for idempotency.
- **Input bounds** — `image_base64` capped at 8 MB body / 5 MB decoded (413); `food_name ≤ 120`, `calories 0..20000`, `image_b64 ≤ 250 KB`; passwords ≥ 8 chars.
- **Error hygiene** — Gemini failures return generic 502 (no provider details).

## Razorpay (LIVE keys configured)
- `RAZORPAY_KEY_ID=rzp_test_TNKjZ4cPbJPYfp`
- `RAZORPAY_KEY_SECRET` set in backend/.env
- `RAZORPAY_PLAN_ID=plan_TNKpaaAmmoDt7u` (₹57/month, INR)
- `RAZORPAY_WEBHOOK_SECRET` is now a strong random (real). Add a webhook in Razorpay Dashboard → Webhooks pointing to `https://nutrition-simple-7.preview.emergentagent.com/api/subscription/webhook` and paste the SAME value shown in `backend/.env` when creating the webhook so signatures verify.
