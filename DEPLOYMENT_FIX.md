# 🔧 Fix for 401 Authentication Errors

## Problem Diagnosis

The logs show:
```
Unauthorized: /api/auth/refresh/
Unauthorized: /api/auth/login/
Bad Request: /api/documents/upload/
```

### Root Causes:

1. **CORS configuration issue** - Vercel frontend (`https://angel-ai-gamma.vercel.app`) not in CORS_ALLOWED_ORIGINS
2. **SameSite cookie problem** - Production uses `SameSite=None` which requires HTTPS and proper CORS
3. **Missing CORS_ALLOWED_ORIGINS on Render** - Only set to localhost in current config

---

## ✅ Solution: Add Environment Variable on Render

### Go to Render Dashboard → Your Backend Service → Environment

Add this variable:

**Key:** `CORS_ALLOWED_ORIGINS`  
**Value:** `https://angel-ai-gamma.vercel.app,https://angel-ai-gamma.vercel.app/`

(Note: Include both with and without trailing slash for safety)

---

## Alternative: Allow All Vercel Apps

If you want to allow all your Vercel deployments (including preview branches):

The regex pattern in settings.py already handles this:
```python
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.vercel\.app$",
]
```

This should work, but let's verify the CORS middleware is configured correctly.

---

## Quick Test

After adding the environment variable:

1. Render will auto-redeploy (2-3 minutes)
2. Try logging in at https://angel-ai-gamma.vercel.app
3. Check browser console (F12) → Network tab
4. Look for:
   - `Access-Control-Allow-Origin: https://angel-ai-gamma.vercel.app` in response headers
   - Successful 200 response on `/api/auth/login/`

---

## If Still Not Working

Check these additional issues:

### 1. Browser Console Errors
Open browser DevTools (F12) → Console tab  
Look for CORS errors like:
```
Access to XMLHttpRequest blocked by CORS policy
```

### 2. Check if JWT token is being sent
Network tab → Click on failed request → Headers tab  
Should see:
```
Authorization: Bearer eyJ0eXAiOiJKV1...
```

### 3. Verify cookies are set
Application tab → Cookies → https://angel-ai-gamma.vercel.app  
Should see:
```
angelai_refresh = [some long string]
```

---

## Debug: Check Render Logs

If the issue persists, check Render logs for:

```bash
# Good - CORS working
"POST /api/auth/login/ HTTP/1.1" 200

# Bad - CORS blocked
"OPTIONS /api/auth/login/ HTTP/1.1" 403

# Bad - No auth token
Unauthorized: /api/auth/login/
```

---

## Current Render Environment Variables Needed

Make sure ALL these are set on Render:

```bash
# Django
DEBUG=False
DJANGO_SECRET_KEY=<your-strong-random-secret>
ALLOWED_HOSTS=angel-ai-cak5.onrender.com
CORS_ALLOWED_ORIGINS=https://angel-ai-gamma.vercel.app

# Database (auto-set by Render if using Render PostgreSQL)
DATABASE_URL=<auto-set-by-render>

# Gemini (embeddings only)
GEMINI_API_KEY=<your-gemini-key>
GEMINI_EMBEDDING_MODEL=gemini-embedding-001

# Groq (primary LLM)
GROQ_API_KEY=<your-NEW-rotated-groq-key>
GROQ_MODEL=llama-3.3-70b-versatile

# OpenRouter (fallback LLM)
OPENROUTER_API_KEY=<your-NEW-rotated-openrouter-key>
OPENROUTER_FREE_MODELS=meta-llama/llama-3.1-8b-instruct:free,qwen/qwen-2.5-7b-instruct:free,mistralai/mistral-7b-instruct:free,x-ai/grok-beta:free

# Redis (optional)
REDIS_URL=<your-redis-url-if-using>
```

---

## Still Getting 400 on Upload?

The "Bad Request: /api/documents/upload/" error means:
- Either "No file provided" 
- Or "session_id is required"

This is likely a frontend issue sending the FormData incorrectly.

Check your upload component is sending:
```javascript
const formData = new FormData();
formData.append('file', fileObject);
formData.append('session_id', sessionId);

// With Authorization header
headers: {
  'Authorization': `Bearer ${accessToken}`
}
```

---

## Summary: Step-by-Step Fix

1. [ ] Add `CORS_ALLOWED_ORIGINS=https://angel-ai-gamma.vercel.app` to Render
2. [ ] Wait for auto-redeploy (2-3 minutes)
3. [ ] Test login at your Vercel URL
4. [ ] If still failing, check browser console for specific CORS error
5. [ ] If upload fails, check FormData is including file + session_id
