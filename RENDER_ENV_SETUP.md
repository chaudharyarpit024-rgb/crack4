# Render Deployment Environment Variables Guide

This guide contains all environment variables and configuration needed to deploy the **CRACK Backend** to [Render](https://render.com).

---

## 🚀 1. Render Service Configuration

When creating your **Web Service** on Render:

| Setting | Value |
| :--- | :--- |
| **Language / Runtime** | `Python 3` or `Docker` |
| **Root Directory** | `backend` |
| **Build Command** | `pip install -r requirements.txt gunicorn` |
| **Start Command** | `gunicorn -w 4 -k uvicorn.workers.UvicornWorker server:app --bind 0.0.0.0:$PORT` |
| **Health Check Path** | `/` |

---

## 📋 2. Environment Variables to Paste into Render

Go to **Render Dashboard** → Your Web Service → **Environment** tab → Click **"Add from .env"** or paste the following into the Environment editor:

```env
# Database
MONGO_URL=mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/crack?retryWrites=true&w=majority
DB_NAME=crack

# Security (MUST be >= 32 characters, no 'placeholder' word)
JWT_SECRET=your_32_plus_char_strong_random_secret_here

# Service URLs
PUBLIC_API_URL=https://<your-render-service-name>.onrender.com
MOBILE_RETURN_URL=crack://razorpay-complete

# AI / Nutrition Analysis (Gemini / Emergent)
EMERGENT_LLM_KEY=your_gemini_or_emergent_api_key_here

# Payments & Subscriptions (Razorpay)
RAZORPAY_KEY_ID=rzp_live_xxxxxxxxxxxxxx
RAZORPAY_KEY_SECRET=your_razorpay_key_secret_here
RAZORPAY_WEBHOOK_SECRET=your_razorpay_webhook_secret_here
RAZORPAY_PLAN_ID=plan_xxxxxxxxxxxxxx
SUBSCRIPTION_AMOUNT_PAISE=3900
SUBSCRIPTION_TRIAL_DAYS=10

# Email & Verification (Brevo / SMTP)
SMTP_DRY_RUN=0
BREVO_API_KEY=xkeysib-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SMTP_FROM=no-reply@yourdomain.com
EMAIL_VERIFY_TTL_HOURS=24
RESEND_MIN_INTERVAL_SECONDS=60
```

---

## 🔍 3. Detailed Field Descriptions

### Database
- **`MONGO_URL`** *(Required)*: MongoDB Atlas connection string.
  > ⚠️ **Important**: In MongoDB Atlas, go to **Network Access** and add `0.0.0.0/0` (Allow Access from Anywhere) so Render dynamic IP addresses can connect.
- **`DB_NAME`** *(Optional, default: `crack`)*: Target database name.

### Authentication & Security
- **`JWT_SECRET`** *(Required)*: Random secret for JWT authentication.
  > ⚠️ **Rule**: Must be at least **32 characters long**. The backend enforces this on startup and will throw an error if the secret is weak or contains "placeholder".
  > Generate one in terminal: `openssl rand -hex 32`

### Public URLs
- **`PUBLIC_API_URL`** *(Required)*: Full HTTPS URL of your Render backend service (e.g. `https://crack4-backend.onrender.com`). Used for email verification links and callbacks.
- **`MOBILE_RETURN_URL`** *(Default: `crack://razorpay-complete`)*: App scheme to return to after user checkout.

### AI Nutrition Scanner
- **`EMERGENT_LLM_KEY`** *(Required for Food Analysis)*: Gemini / Emergent API key used by the photo macro estimation endpoint (`/api/food/analyze`).

### Razorpay Subscriptions
- **`RAZORPAY_KEY_ID`**: Public Razorpay Key (`rzp_live_...` or `rzp_test_...`).
- **`RAZORPAY_KEY_SECRET`**: Private Razorpay Key Secret.
- **`RAZORPAY_WEBHOOK_SECRET`**: Webhook secret to verify incoming event signatures at `/api/subscriptions/webhook`.
- **`RAZORPAY_PLAN_ID`**: Recurring subscription Plan ID created in your Razorpay Dashboard.
- **`SUBSCRIPTION_AMOUNT_PAISE`**: Price in paise (`3900` = ₹39.00).
- **`SUBSCRIPTION_TRIAL_DAYS`**: Free trial period duration in days (`10`).

### Email & Verification
- **`SMTP_DRY_RUN`**: Set to `0` for production so emails actually send. If `1`, emails are simulated and logged to container output.
- **`BREVO_API_KEY`**: Brevo (formerly Sendinblue) API key. Operates over HTTPS Port 443, avoiding port blocks common on cloud hosts.
- **`SMTP_FROM`**: The sender email address shown to users (e.g. `no-reply@yourdomain.com`).
- **`EMAIL_VERIFY_TTL_HOURS`**: Link validity in hours (default: `24`).
- **`RESEND_MIN_INTERVAL_SECONDS`**: Cooldown in seconds before a user can request another verification email (default: `60`).
