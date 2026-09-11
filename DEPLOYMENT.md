# Angel AI - Deployment Guide

## Local Development Setup

### Backend

1. **Install dependencies:**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Set environment variables:**
   ```bash
   export GEMINI_API_KEY="your-gemini-api-key"
   export DEBUG="True"
   export REDIS_URL="redis://localhost:6379/0"  # Optional
   ```

3. **Run migrations:**
   ```bash
   python manage.py migrate
   ```

4. **Start development server:**
   ```bash
   python manage.py runserver
   ```

### Redis (Optional for Caching)

```bash
# Using Docker
docker run -d -p 6379:6379 redis:7-alpine

# Or install locally
brew install redis  # macOS
redis-server
```

### Frontend

1. **Install dependencies:**
   ```bash
   cd frontend
   npm install
   ```

2. **Update environment:**
   ```typescript
   // frontend/src/environments/environment.ts
   export const environment = {
     production: false,
     apiUrl: 'http://localhost:8000'
   };
   ```

3. **Start development server:**
   ```bash
   npm start
   ```

---

## Production Deployment

### Render (Backend)

1. **Create Web Service:**
   - Connect your GitHub repo
   - Set Root Directory: `backend`
   - Build Command: `pip install -r requirements.txt && python manage.py migrate`
   - Start Command: `gunicorn --pythonpath . config.wsgi:application --bind 0.0.0.0:$PORT --timeout 120 --workers 2`

2. **Environment Variables:**
   ```
   PYTHON_VERSION=3.11
   GEMINI_API_KEY=<your-key>
   DJANGO_SECRET_KEY=<generate-random-string>
   DEBUG=False
   ALLOWED_HOSTS=your-app.onrender.com
   ```

3. **Optional - Add Redis:**
   - Create Redis instance on Render
   - Add `REDIS_URL` environment variable

4. **Optional - Add PostgreSQL:**
   - Create PostgreSQL database
   - Add `DATABASE_URL` environment variable (auto-populated by Render)

### Vercel (Frontend)

1. **Deploy:**
   ```bash
   cd frontend
   npm run build
   vercel --prod
   ```

2. **Environment Variables:**
   ```
   VITE_API_URL=https://your-backend.onrender.com
   ```

3. **Update environment.prod.ts:**
   ```typescript
   export const environment = {
     production: true,
     apiUrl: 'https://your-backend.onrender.com'
   };
   ```

---

## Google Cloud Setup

### Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create API key
3. **Important:** Remove HTTP referrer restrictions for backend use
   - Go to Google Cloud Console → Credentials
   - Edit your API key
   - Under "Application restrictions": Select "None"
   - Under "API restrictions": Enable only "Generative Language API"

---

## Health Check

Once deployed, verify:

```bash
curl https://your-backend.onrender.com/health/
```

Expected response:
```json
{
  "status": "healthy",
  "database": "configured",
  "media_dir": "/path/to/media",
  "media_writable": true,
  "gemini_key": "configured",
  "debug": false
}
```

---

## Monitoring

### Key Metrics to Monitor

1. **Cache Hit Rate:**
   - Check `cached` field in API responses
   - Target: >50% for repeat queries

2. **Response Times:**
   - Cached: <100ms
   - Uncached: 2-5s (Gemini API latency)

3. **Error Rates:**
   - Watch for ChromaDB connection errors
   - Monitor Gemini API quota/errors

### Logs

**Backend (Render):**
- View logs in Render dashboard
- Look for `ERROR` or `WARNING` messages

**Frontend (Vercel):**
- Check browser console for errors
- Monitor network tab for failed API calls

---

## Troubleshooting

### Issue: "No relevant information found"
**Cause:** Document not yet processed or ChromaDB query returns empty
**Fix:** 
- Check document status: `GET /api/documents/<id>/status/`
- Verify embeddings stored in ChromaDB
- Try uploading document again

### Issue: Redis connection errors
**Cause:** Redis not available or wrong URL
**Fix:**
- System will work without Redis (no caching)
- Check `REDIS_URL` environment variable
- Verify Redis service is running

### Issue: Gemini API 403 errors
**Cause:** API key restrictions blocking server requests
**Fix:**
- Remove HTTP referrer restrictions
- Set "Application restrictions" to "None"
- Verify API key is valid

### Issue: Upload fails with 500 error
**Cause:** Database not migrated or file permissions
**Fix:**
- Run migrations: `python manage.py migrate`
- Check media directory permissions
- View backend logs for specific error

### Issue: ChromaDB import error
**Cause:** numpy version incompatibility
**Fix:**
- Ensure numpy 1.x: `pip install "numpy>=1.24,<2.0"`
- Use Python 3.11 (not 3.14)

---

## Scaling Considerations

### Performance

**Current limits:**
- ~1000 documents per session
- ~10,000 chunks in ChromaDB (before slowdown)
- Free tier Render: 512MB RAM

**If scaling needed:**

1. **Use PostgreSQL instead of SQLite**
   - Add DATABASE_URL to Render

2. **Add Redis for caching**
   - Reduces Gemini API calls by 50-80%
   - Speeds up repeat queries

3. **Upgrade to paid Render plan**
   - More RAM for ChromaDB
   - Better performance

4. **Consider external vector DB**
   - Pinecone, Weaviate, or Qdrant Cloud
   - Better for >100k documents

### Cost Optimization

1. **Cache hits reduce Gemini API costs**
   - Embedding: $0.00025/1K tokens
   - Generation: $0.001/1K tokens
   - Cache can save 50-80% of costs

2. **Free tiers:**
   - Render: Free web service (spins down on idle)
   - Vercel: Free hosting
   - Google Gemini: Free quota available

---

## Security Checklist

- [ ] `DEBUG=False` in production
- [ ] Strong `DJANGO_SECRET_KEY`
- [ ] HTTPS enabled (automatic on Render/Vercel)
- [ ] API key stored in environment variables (not code)
- [ ] Gemini API key restrictions configured
- [ ] `ALLOWED_HOSTS` properly set
- [ ] CORS configured for frontend domain
- [ ] File upload size limits enforced (20MB)
- [ ] Input validation on all endpoints

---

## Backup & Recovery

### ChromaDB Data
Location: `backend/chroma_db/`

**Backup:**
```bash
# On Render, use persistent disk or external storage
tar -czf chroma_backup.tar.gz backend/chroma_db/
```

**Restore:**
```bash
tar -xzf chroma_backup.tar.gz
```

### Database
- SQLite: Backup `backend/db.sqlite3`
- PostgreSQL: Use Render's automatic backups

---

## Support

For issues:
1. Check health endpoint
2. Review backend logs
3. Verify environment variables
4. Test with curl/Postman
5. Check browser console for frontend errors
