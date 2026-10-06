import { Component, Input, OnInit, OnChanges, AfterViewInit, ElementRef, ViewChild, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AiFeaturesService, Roadmap } from '../shared/services/ai-features.service';
import mermaid from 'mermaid';

@Component({
  selector: 'app-roadmap',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './roadmap.component.html',
  styleUrl: './roadmap.component.scss'
})
export class RoadmapComponent implements OnInit, OnChanges, AfterViewInit {
  @Input() documentId: string = '';
  @ViewChild('mermaidContainer') mermaidContainer!: ElementRef;

  roadmap: Roadmap | null = null;
  isLoading: boolean = false;
  isGenerating: boolean = false;
  errorMessage: string = '';
  renderError: string = '';

  constructor(private aiService: AiFeaturesService) {
    // Initialize Mermaid
    mermaid.initialize({
      startOnLoad: false,
      theme: 'default',
      securityLevel: 'loose',
      fontFamily: 'system-ui, -apple-system, sans-serif'
    });
  }

  ngOnInit(): void {
    if (this.documentId) {
      this.loadRoadmap();
    }
  }

  ngAfterViewInit(): void {
    // Render will happen after data is loaded
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['documentId'] && !changes['documentId'].firstChange && this.documentId) {
      this.roadmap = null;
      this.loadRoadmap();
    }
  }

  loadRoadmap(): void {
    this.isLoading = true;
    this.errorMessage = '';
    this.renderError = '';
    
    this.aiService.getRoadmap(this.documentId).subscribe({
      next: (response) => {
        this.roadmap = response.roadmap;
        this.isLoading = false;
        
        if (!this.roadmap) {
          // Auto-generate if none exists
          this.generateRoadmap();
        } else {
          // Render the diagram
          setTimeout(() => this.renderMermaid(), 100);
        }
      },
      error: (err) => {
        this.errorMessage = err?.error?.error || 'Failed to load roadmap';
        this.isLoading = false;
      }
    });
  }

  generateRoadmap(): void {
    this.isGenerating = true;
    this.errorMessage = '';
    this.renderError = '';
    
    this.aiService.generateRoadmap(this.documentId).subscribe({
      next: (response) => {
        this.roadmap = response.roadmap;
        this.isGenerating = false;
        
        // Render the diagram
        setTimeout(() => this.renderMermaid(), 100);
      },
      error: (err) => {
        this.errorMessage = err?.error?.error || 'Failed to generate roadmap. Please try again.';
        this.isGenerating = false;
      }
    });
  }

  regenerateRoadmap(): void {
    if (!confirm('Delete existing roadmap and generate a new one?')) {
      return;
    }

    this.isGenerating = true;
    this.errorMessage = '';
    this.renderError = '';

    this.aiService.deleteRoadmap(this.documentId).subscribe({
      next: () => {
        this.generateRoadmap();
      },
      error: (err) => {
        this.errorMessage = err?.error?.error || 'Failed to delete roadmap';
        this.isGenerating = false;
      }
    });
  }

  async renderMermaid(): Promise<void> {
    if (!this.roadmap || !this.mermaidContainer) {
      return;
    }

    try {
      const container = this.mermaidContainer.nativeElement;
      container.innerHTML = '';
      
      // Create a unique ID for this diagram
      const id = `mermaid-${Date.now()}`;
      
      // Render the diagram
      const { svg } = await mermaid.render(id, this.roadmap.mermaid_definition);
      
      // Insert the SVG
      container.innerHTML = svg;
      
      this.renderError = '';
    } catch (error: any) {
      console.error('Mermaid render error:', error);
      this.renderError = 'Failed to render diagram. The syntax may be invalid.';
    }
  }
}
