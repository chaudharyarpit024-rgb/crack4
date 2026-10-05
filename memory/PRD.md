# CRACK - Competitive Fitness & Personalized Nutrition Platform

## Overview
CRACK is divided into two distinct tiers:
1. **Free Tier (Competitive Dashboard):** A competitive fitness platform where users register their profile, view their BMI, and compete against others in Gym weightlifting (PRs, SBD total, relative strength) and Sports activities (running, cycling, steps, streaks).
2. **Subscription Tier (Personalized Health & Guild Suite):** Unlocked via subscription. Gathers specific intake (Weight Decision, Food Type, Optional Medical Record) to deliver AI-powered Calorie Counter (camera scan + macros), Food & Recipe Suggestions, Personalization, Exercise routines, Family Challenges (Guilds), and Advanced Multi-Metric Rankings.

## Tech
- **Frontend:** Expo Router (React Native), TypeScript
- **Backend:** FastAPI + MongoDB (Motor)
- **Auth:** JWT (email + password, bcrypt) + unique @username
- **AI:** Gemini 3 Flash via Emergent Universal LLM key
- **Camera:** expo-camera + expo-image-manipulator
- **Payments:** Razorpay Subscriptions (autopay)

## Features & Architecture

### 1. Free Tier
- **Auth & Profile:** Email, Name, Password, DOB, Age (calculated), Weight (kg), Height (cm), Gender, Unique @Username, Profile Photo.
- **BMI Calculator:** Dynamic calculation ($\text{weight} / \text{height}^2$), category classification (Underweight, Normal, Overweight, Obese), and healthy range visualization.
- **Competitive Dashboard (Leaderboard):**
  - **Physical: Gym:** Bench Press, Squat, Deadlift, Overhead Press, SBD Total, Relative Strength ratio ($\text{Total} / \text{Bodyweight}$).
  - **Sports & Cardio:** Running (distance/pace), Cycling, Swimming, Daily steps, Workout streaks.
  - Global, weight-class, and gender-filtered leaderboards with podium rankings.

### 2. Subscription Tier
- **Subscription Intake:**
  - **Weight Decision:** Fat loss / Muscle gain / Recomp / Maintenance + target weight & pace.
  - **Food Type:** Vegetarian, Vegan, Eggetarian, Non-Veg, Keto, Jain, Halal, etc.
  - **Medical Record (Optional):** Allergies (nuts, lactose, gluten), Conditions (diabetes, PCOS, thyroid), Physical injuries.
- **Calorie Counter:** AI camera food scanning (Gemini Vision) + manual search & log + calorie & macro rings (protein, carbs, fat, fiber).
- **Food & Recipe Suggestions:** AI meal recommendations tailored to remaining calories, dietary preferences, and allergy exclusions.
- **Personalization:** Adaptive calorie/macro adjustments and metabolic pacing.
- **Exercise:** Goal-matched workout routines with injury-aware exercise substitutions.
- **Family Challenge (Guild):** Create or join private guilds, collaborate on group challenges (steps, workout streaks, diet compliance).
- **Rank & All:** Guild leaderboards, multi-factor achievement badges, and seasonal league tiers.

## Backend Endpoints Overview
- **Auth:** `POST /api/auth/signup`, `POST /api/auth/login`, `GET /api/auth/me`
- **Profile & BMI:** `PUT /api/profile`, `GET /api/profile/{username}`
- **Competition & Leaderboard (Free):**
  - `POST /api/compete/gym` (log/update 1RM lifts)
  - `GET /api/compete/gym/leaderboard` (filter by lift, gender, weight class)
  - `POST /api/compete/sports` (log run, cycling, steps)
  - `GET /api/compete/sports/leaderboard`
- **Subscription Intake & Gated Features (Subscription):**
  - `PUT /api/subscription/intake` (weight decision, food type, medical record)
  - `POST /api/food/analyze` (AI camera scanner, gated)
  - `POST /api/food/log`, `GET /api/food/today`, `GET /api/food/history`, `DELETE /api/food/{id}`
  - `GET /api/nutrition/recipes` (personalized meal suggestions)
  - `GET /api/exercise/routines` (personalized workout routines)
  - `GET /api/guild/me`, `POST /api/guild/create`, `POST /api/guild/join`, `GET /api/guild/leaderboard`
- **Subscription Billing:** `GET /api/subscription/me`, `POST /api/subscription/checkout`, `GET /api/subscription/checkout-page`, `POST /api/subscription/callback`, `POST /api/subscription/webhook`

## Screens
- **Free:** `/` splash → gate • `/login` • `/signup` • `/(tabs)/leaderboard` • `/(tabs)/profile` • `/log-lift` • `/log-sport` • `/terms` • `/privacy`
- **Subscription / Gated:** `/(tabs)/nutrition` • `/camera` • `/analyze` • `/manual` • `/recipes` • `/exercise` • `/(tabs)/guild` • `/subscribe` • `/subscription-intake`



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
