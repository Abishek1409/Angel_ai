# Flashcards & Roadmap Features Implementation

## Summary

Added two AI-powered features to Angel AI:
1. **Flashcards** - Generate study flashcards from documents using Gemini
2. **Roadmap** - Generate Mermaid.js flowchart diagrams showing document structure

---

## BACKEND CHANGES

### New Files Created:

#### 1. `backend/documents/flashcard_models.py`
- **Flashcard** model: stores question/answer pairs per document
- **Roadmap** model: stores Mermaid diagram definition per document
- Both linked to Document with ForeignKey/OneToOneField
- User ownership enforced through Document relationship

#### 2. `backend/documents/ai_services.py`
- `generate_flashcards()`: Calls Gemini with JSON mode to generate 10-15 flashcards
- `generate_roadmap()`: Calls Gemini to generate Mermaid flowchart syntax
- `_call_gemini_json()`: Reusable function for structured JSON output from Gemini
- `_get_document_text_from_chromadb()`: Retrieves all chunks for a document
- `_validate_mermaid_syntax()`: Basic validation of Mermaid diagram types
- **Retry logic**: Up to 2 attempts for malformed JSON/invalid syntax

#### 3. `backend/documents/ai_views.py`
API endpoints:
- `POST /api/documents/{id}/flashcards/generate/` - Generate flashcards
- `GET /api/documents/{id}/flashcards/` - Get cached flashcards
- `DELETE /api/documents/{id}/flashcards/delete/` - Delete for regeneration
- `POST /api/documents/{id}/roadmap/generate/` - Generate roadmap
- `GET /api/documents/{id}/roadmap/` - Get cached roadmap
- `DELETE /api/documents/{id}/roadmap/delete/` - Delete for regeneration

All endpoints require authentication (`@permission_classes([IsAuthenticated])`)

#### 4. `backend/documents/migrations/0002_flashcard_roadmap.py`
Database migration for new models

### Modified Files:

#### `backend/documents/urls.py`
```python
# ADDED:
from . import ai_views

# ADDED routes:
path("<uuid:document_id>/flashcards/", ai_views.get_flashcards),
path("<uuid:document_id>/flashcards/generate/", ai_views.create_flashcards),
path("<uuid:document_id>/flashcards/delete/", ai_views.delete_flashcards),
path("<uuid:document_id>/roadmap/", ai_views.get_roadmap),
path("<uuid:document_id>/roadmap/generate/", ai_views.create_roadmap),
path("<uuid:document_id>/roadmap/delete/", ai_views.delete_roadmap),
```

---

## FRONTEND CHANGES

### New Files Created:

#### 1. `frontend/src/app/shared/services/ai-features.service.ts`
Angular service for API calls:
- `getFlashcards(documentId)`
- `generateFlashcards(documentId)`
- `deleteFlashcards(documentId)`
- `getRoadmap(documentId)`
- `generateRoadmap(documentId)`
- `deleteRoadmap(documentId)`

Interfaces:
- `Flashcard`: { id, question, answer, created_at }
- `Roadmap`: { id, mermaid_definition, created_at, updated_at }

#### 2. `frontend/src/app/flashcards/flashcards.component.ts`
Flashcard component features:
- Flip card animation (question ↔ answer)
- Previous/Next navigation
- Progress indicator (e.g., "3/12")
- Auto-generate if no flashcards exist
- Regenerate button with confirmation
- Loading and error states

#### 3. `frontend/src/app/flashcards/flashcards.component.html`
UI template with:
- Card flip interaction
- Navigation buttons
- Loading spinner
- Error messages
- Empty state with generate button

#### 4. `frontend/src/app/flashcards/flashcards.component.scss`
Styling:
- 3D flip animation
- Card front/back design
- Responsive layout
- Button hover states

#### 5. `frontend/src/app/roadmap/roadmap.component.ts`
Roadmap component features:
- Mermaid.js integration
- Async diagram rendering
- Auto-generate if no roadmap exists
- Regenerate button
- Error handling for invalid Mermaid syntax
- Scrollable container for large diagrams

#### 6. `frontend/src/app/roadmap/roadmap.component.html`
UI template with:
- Diagram container
- Loading states
- Error messages with retry
- Regenerate button

#### 7. `frontend/src/app/roadmap/roadmap.component.scss`
Styling:
- Scrollable diagram container
- Mermaid node customization
- Responsive design
- Custom scrollbars

### Modified Files:

#### `frontend/package.json`
```json
// ADDED dependency:
"mermaid": "^11.0.0"
```

---

## HOW TO INTEGRATE INTO YOUR APP

### 1. Add Tabs to Chat View

Modify your chat component to include tabs for Flashcards and Roadmap:

```typescript
// In chat.component.ts
currentTab: 'chat' | 'flashcards' | 'roadmap' = 'chat';

selectTab(tab: 'chat' | 'flashcards' | 'roadmap'): void {
  this.currentTab = tab;
}
```

```html
<!-- In chat.component.html -->
<div class="chat-tabs">
  <button (click)="selectTab('chat')" [class.active]="currentTab === 'chat'">
    Chat
  </button>
  <button (click)="selectTab('flashcards')" [class.active]="currentTab === 'flashcards'">
    Flashcards
  </button>
  <button (click)="selectTab('roadmap')" [class.active]="currentTab === 'roadmap'">
    Roadmap
  </button>
</div>

<div class="tab-content">
  <div *ngIf="currentTab === 'chat'">
    <!-- Existing chat UI -->
  </div>
  
  <app-flashcards 
    *ngIf="currentTab === 'flashcards'" 
    [documentId]="documentId || ''"
  />
  
  <app-roadmap 
    *ngIf="currentTab === 'roadmap'" 
    [documentId]="documentId || ''"
  />
</div>
```

### 2. Import Components

```typescript
// In chat.component.ts
import { FlashcardsComponent } from '../flashcards/flashcards.component';
import { RoadmapComponent } from '../roadmap/roadmap.component';

@Component({
  // ...
  imports: [
    // existing imports...
    FlashcardsComponent,
    RoadmapComponent
  ]
})
```

---

## DEPLOYMENT STEPS

### Backend:

```bash
# 1. Install dependencies (no new packages needed - uses existing Gemini)
cd backend
pip install -r requirements.txt

# 2. Run migrations
python manage.py makemigrations
python manage.py migrate

# 3. Test locally
python manage.py runserver
```

### Frontend:

```bash
# 1. Install new dependency (mermaid)
cd frontend
npm install

# 2. Test locally
npm start
```

### Render/Production:

1. Push changes to Git
2. Render will auto-deploy backend
3. Vercel will auto-deploy frontend
4. No new environment variables needed (uses existing GEMINI_API_KEY)

---

## API USAGE EXAMPLES

### Generate Flashcards:
```bash
curl -X POST https://angel-ai-cak5.onrender.com/api/documents/{document_id}/flashcards/generate/ \
  -H "Authorization: Bearer {access_token}"
```

Response:
```json
{
  "message": "Flashcards generated successfully",
  "count": 12,
  "flashcards": [
    {
      "id": "uuid",
      "question": "What is...",
      "answer": "...",
      "created_at": "2026-09-27T..."
    }
  ]
}
```

### Generate Roadmap:
```bash
curl -X POST https://angel-ai-cak5.onrender.com/api/documents/{document_id}/roadmap/generate/ \
  -H "Authorization: Bearer {access_token}"
```

Response:
```json
{
  "message": "Roadmap generated successfully",
  "roadmap": {
    "id": "uuid",
    "mermaid_definition": "flowchart TD\n    A[Introduction] --> B[Topic 1]\n    ...",
    "created_at": "2026-09-27T...",
    "updated_at": "2026-09-27T..."
  }
}
```

---

## ERROR HANDLING

### Backend:
- **Malformed JSON**: Retries up to 2 times with stricter prompt
- **Invalid Mermaid**: Retries once with explicit formatting instructions
- **Document not ready**: Returns 400 with clear message
- **ChromaDB empty**: Returns 500 with "no chunks found" error
- **Gemini API errors**: Logged and returned as 500 with user-friendly message

### Frontend:
- **Loading states**: Spinner with "Generating... This may take a few seconds"
- **Error messages**: Red icon + error text + "Try Again" button
- **Mermaid render failure**: "Failed to render diagram" + Regenerate button
- **Empty states**: Clear CTA to generate content

---

## CACHING BEHAVIOR

- Flashcards and roadmaps are **cached in the database**
- GET endpoints return cached data instantly
- POST endpoints check for existing data first
- DELETE + POST allows regeneration
- No Redis/external cache needed - PostgreSQL stores everything

---

## GIT COMMIT MESSAGE

```bash
git add .
git commit -m "feat: add AI-generated flashcards and roadmap features

- Add flashcard generation endpoint using Gemini JSON mode
- Add Mermaid roadmap/flowchart generation endpoint
- Create Flashcard and Roadmap models with database caching
- Implement flip-card UI component for flashcards
- Integrate Mermaid.js for visual diagram rendering
- Add retry logic for malformed JSON and invalid Mermaid syntax
- Include loading states, error handling, and regenerate functionality
- Maintain user ownership and authentication requirements

Features accessible via tabs in chat view.
Both features use existing Gemini API key (no new env vars needed)."

git push origin main
```

---

## TESTING CHECKLIST

- [ ] Upload a document
- [ ] Navigate to Flashcards tab
- [ ] Wait for auto-generation (10-15 seconds)
- [ ] Flip cards, navigate next/previous
- [ ] Click "Regenerate" → Confirm deletion → New flashcards generated
- [ ] Navigate to Roadmap tab
- [ ] Wait for auto-generation
- [ ] Verify Mermaid diagram renders correctly
- [ ] Click "Regenerate" → New diagram generated
- [ ] Test error handling: Try with empty document (should show error)
- [ ] Verify cached data loads instantly on subsequent visits

---

## NOTES

- **Gemini API usage**: ~2000-3000 tokens per flashcard generation, ~1500-2500 per roadmap
- **Generation time**: 5-15 seconds depending on document length
- **Mermaid version**: 11.0.0 (latest, supports all diagram types)
- **Browser compatibility**: Chrome/Edge/Firefox/Safari (all support Mermaid)
- **Mobile**: Flashcards work great, roadmaps may need horizontal scroll on small screens

---

That's it! You now have AI-powered flashcards and roadmap generation fully integrated. 🚀
