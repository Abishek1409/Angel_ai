import { Component, Input, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AiFeaturesService, Flashcard } from '../shared/services/ai-features.service';

@Component({
  selector: 'app-flashcards',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './flashcards.component.html',
  styleUrl: './flashcards.component.scss'
})
export class FlashcardsComponent implements OnInit {
  @Input() documentId: string = '';

  flashcards: Flashcard[] = [];
  currentIndex: number = 0;
  isFlipped: boolean = false;
  isLoading: boolean = false;
  isGenerating: boolean = false;
  errorMessage: string = '';

  constructor(private aiService: AiFeaturesService) {}

  ngOnInit(): void {
    if (this.documentId) {
      this.loadFlashcards();
    }
  }

  loadFlashcards(): void {
    this.isLoading = true;
    this.errorMessage = '';
    
    this.aiService.getFlashcards(this.documentId).subscribe({
      next: (response) => {
        this.flashcards = response.flashcards;
        this.isLoading = false;
        
        if (this.flashcards.length === 0) {
          // Auto-generate if none exist
          this.generateFlashcards();
        }
      },
      error: (err) => {
        this.errorMessage = err?.error?.error || 'Failed to load flashcards';
        this.isLoading = false;
      }
    });
  }

  generateFlashcards(): void {
    this.isGenerating = true;
    this.errorMessage = '';
    
    this.aiService.generateFlashcards(this.documentId).subscribe({
      next: (response) => {
        this.flashcards = response.flashcards;
        this.currentIndex = 0;
        this.isFlipped = false;
        this.isGenerating = false;
      },
      error: (err) => {
        this.errorMessage = err?.error?.error || 'Failed to generate flashcards. Please try again.';
        this.isGenerating = false;
      }
    });
  }

  regenerateFlashcards(): void {
    if (!confirm('Delete existing flashcards and generate new ones?')) {
      return;
    }

    this.isGenerating = true;
    this.errorMessage = '';

    this.aiService.deleteFlashcards(this.documentId).subscribe({
      next: () => {
        this.generateFlashcards();
      },
      error: (err) => {
        this.errorMessage = err?.error?.error || 'Failed to delete flashcards';
        this.isGenerating = false;
      }
    });
  }

  flipCard(): void {
    this.isFlipped = !this.isFlipped;
  }

  nextCard(): void {
    if (this.currentIndex < this.flashcards.length - 1) {
      this.currentIndex++;
      this.isFlipped = false;
    }
  }

  previousCard(): void {
    if (this.currentIndex > 0) {
      this.currentIndex--;
      this.isFlipped = false;
    }
  }

  get currentCard(): Flashcard | null {
    return this.flashcards[this.currentIndex] || null;
  }

  get progress(): string {
    if (this.flashcards.length === 0) return '0/0';
    return `${this.currentIndex + 1}/${this.flashcards.length}`;
  }
}
