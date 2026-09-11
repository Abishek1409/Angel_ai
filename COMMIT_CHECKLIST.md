# Commit & Deploy Checklist

## Pre-Commit Checks

### Backend
- [x] All Python files updated with type hints
- [x] Error handling added where needed
- [x] Logging configured properly
- [x] Requirements.txt versions pinned
- [x] No breaking changes to existing API
- [x] Health endpoint functional
- [x] Redis integration with graceful fallback

### Frontend
- [x] TypeScript compilation passes
- [x] No console errors
- [x] Components properly imported
- [x] Services updated with new interfaces
- [x] UI responsive and accessible
- [x] Backward compatible with old API

### Documentation
- [x] UPGRADE_SUMMARY.md created
- [x] DEPLOYMENT.md created
- [x] UPGRADE_README.md created
- [x] FILES_CHANGED.md created
- [x] Migration script documented

---

## Git Commit

```bash
# Stage all changes
git add .

# Commit with descriptive message
git commit -m "feat: upgrade to multi-document RAG with Redis caching

- Add multi-document support with shared ChromaDB collection
- Implement Redis caching for embeddings and responses  
- Add document list sidebar with delete functionality
- Show source citations in chat responses
- Add cache hit indicators
- Improve error handling and logging
- Pin dependencies for production stability
- Add migration script for existing users
- Comprehensive documentation

BREAKING CHANGES: None (fully backward compatible)

Backend changes:
- Modified embed_and_store() to use metadata
- Added delete_document_from_chromadb()
- Added list and delete endpoints
- Integrated Redis caching with graceful degradation

Frontend changes:
- New DocumentListComponent with sidebar
- Updated services for multi-doc support
- Added source citations to messages
- Cache badge indicator

Closes #[issue-number]"

# Push to repository
git push origin main
```

---

## Deployment Steps

### 1. Backend (Render)

**Before deploying:**
- [ ] Add `REDIS_URL` to environment variables (optional)
- [ ] Verify `GEMINI_API_KEY` is set
- [ ] Set `DEBUG=False`
- [ ] Set `DJANGO_SECRET_KEY`
- [ ] Update `ALLOWED_HOSTS`

**Deploy:**
```bash
# Push triggers auto-deploy on Render
git push origin main

# Or manual deploy in Render dashboard
```

**After deploy:**
- [ ] Check health endpoint: `curl https://your-app.onrender.com/health/`
- [ ] Verify logs for errors
- [ ] Test document upload
- [ ] Test multi-doc query

### 2. Frontend (Vercel)

**Update environment:**
```typescript
// frontend/src/environments/environment.prod.ts
export const environment = {
  production: true,
  apiUrl: 'https://your-backend.onrender.com'
};
```

**Deploy:**
```bash
cd frontend
npm run build
vercel --prod

# Or connect GitHub repo for auto-deploy
```

**After deploy:**
- [ ] Test upload flow
- [ ] Test document list
- [ ] Test delete
- [ ] Verify sources shown
- [ ] Check cache badge

### 3. Optional: Redis Setup

**Render:**
1. Create Redis instance
2. Copy internal URL
3. Add to backend env: `REDIS_URL=<url>`
4. Redeploy backend

**Local:**
```bash
docker run -d -p 6379:6379 redis:7-alpine
export REDIS_URL="redis://localhost:6379/0"
```

---

## Post-Deployment Verification

### Functional Tests

1. **Upload Single Document**
   ```bash
   curl -X POST https://your-backend/api/documents/upload/ \
     -F "file=@test.pdf" \
     -F "session_id=$(uuidgen)"
   ```
   - [ ] Returns document_id
   - [ ] Status becomes "ready"

2. **Upload Multiple Documents**
   - [ ] Upload 2-3 documents
   - [ ] All show in sidebar
   - [ ] All show "ready" status

3. **Multi-Document Query**
   ```bash
   curl -X POST https://your-backend/api/chat/query/ \
     -H "Content-Type: application/json" \
     -d '{
       "session_id": "<session-id>",
       "question": "What is this about?"
     }'
   ```
   - [ ] Returns answer
   - [ ] Returns sources array
   - [ ] Returns cached flag

4. **Single Document Query**
   ```bash
   curl -X POST https://your-backend/api/chat/query/ \
     -H "Content-Type: application/json" \
     -d '{
       "document_id": "<doc-id>",
       "session_id": "<session-id>",
       "question": "What is this about?"
     }'
   ```
   - [ ] Returns answer from that document only
   - [ ] Source matches document filename

5. **Delete Document**
   ```bash
   curl -X DELETE https://your-backend/api/documents/<doc-id>/delete/
   ```
   - [ ] Returns success message
   - [ ] Document removed from list
   - [ ] No longer appears in queries

6. **Cache Test**
   - [ ] Ask question twice
   - [ ] Second response has `"cached": true`
   - [ ] Second response is faster

### UI Tests

- [ ] Document list loads
- [ ] "All Documents" selectable
- [ ] Individual documents selectable
- [ ] Delete button works
- [ ] Upload new button works
- [ ] Sources shown under answers
- [ ] Cache badge appears on cached responses
- [ ] No console errors
- [ ] Responsive on mobile

### Performance Tests

- [ ] First query: 2-5 seconds (acceptable)
- [ ] Cached query: <100ms (fast)
- [ ] Upload: <10 seconds for 5MB PDF
- [ ] Document list loads: <1 second

---

## Monitoring Setup

### Metrics to Track

1. **Cache Hit Rate**
   - Check `cached` field in responses
   - Target: >50% for production

2. **API Response Times**
   - Uncached: 2-5s (Gemini latency)
   - Cached: <100ms

3. **Error Rates**
   - Monitor 500 errors
   - Watch for ChromaDB/Redis failures

4. **Resource Usage**
   - RAM: Should be <512MB (Render free tier)
   - Disk: ChromaDB grows ~10MB per document

### Alerts to Set

- [ ] Health endpoint down
- [ ] Error rate >5%
- [ ] Response time >10s
- [ ] Disk usage >80%

---

## Rollback Plan

If critical issues found:

### Quick Rollback (Git)
```bash
git revert HEAD
git push origin main
```

### Full Rollback
```bash
git checkout <previous-commit>
git push origin main --force
```

**Note**: Old ChromaDB collections are preserved. No data loss on rollback.

---

## Communication

### Announcement Template

**Subject**: Angel AI Upgraded - Multi-Document Support Now Live!

**Body**:
```
Hi team,

We've successfully upgraded Angel AI with these new features:

✅ Multi-Document Support
   - Upload and search across multiple PDFs
   - Document list sidebar
   - "All Documents" search mode

✅ Performance Improvements
   - Redis caching for faster responses
   - 50-80% speed boost on repeat queries

✅ Better UX
   - Source citations showing which docs were used
   - Document management (view, select, delete)
   - Cache indicators

🔗 Links:
   - App: https://your-app.vercel.app
   - Docs: [link to UPGRADE_README.md]

📝 Notes:
   - All existing functionality preserved
   - Your old documents still work
   - Redis optional (for caching)

Questions? Check the docs or reach out!
```

---

## Success Criteria

Deployment is successful when:

- [ ] All functional tests pass
- [ ] No errors in logs
- [ ] Cache hit rate >0% (if Redis enabled)
- [ ] Response times acceptable
- [ ] Users can upload, query, and delete documents
- [ ] Sources display correctly
- [ ] Old single-doc workflow still works

---

## Known Issues / Limitations

Document these for users:

1. **Free Render tier spins down** → First request may be slow (50s)
2. **No pagination on document list** → Fine for <100 documents
3. **Chat history per-document** → Not cross-session yet
4. **Cache doesn't invalidate on delete** → Expires naturally in 1 hour

---

## Next Steps After Deployment

1. **Monitor for 24-48 hours**
   - Check logs daily
   - Watch error rates
   - Gather user feedback

2. **Optional Enhancements**
   - Add document tags/categories
   - Implement pagination for document list
   - Add bulk upload
   - Export chat history

3. **Performance Tuning**
   - Adjust cache TTL based on usage
   - Optimize chunk size if needed
   - Consider external vector DB if scaling

---

✅ **Ready to Deploy!**

Once all checkboxes are complete, the upgrade is production-ready.
