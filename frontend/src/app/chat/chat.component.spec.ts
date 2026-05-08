import { TestBed, ComponentFixture } from '@angular/core/testing';
import { ChatComponent } from './chat.component';
import { ChatService } from '../shared/services/chat.service';
import { provideHttpClient } from '@angular/common/http';
import { of } from 'rxjs';

describe('ChatComponent conversation rendering', () => {
  let fixture: ComponentFixture<ChatComponent>;
  let component: ChatComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ChatComponent],
      providers: [provideHttpClient()],
    }).compileComponents();

    fixture = TestBed.createComponent(ChatComponent);
    component = fixture.componentInstance;
    component.documentId = 'test-doc-id';
    component.sessionId = 'test-session-id';
  });

  it('should render empty state when conversation is empty', () => {
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    const emptyText = compiled.querySelector('.chat-empty');

    expect(component.conversation.length).toBe(0);
    expect(emptyText?.textContent).toContain('Ask a question');
  });

  it('should render conversation history with multiple messages', () => {
    component.conversation = [
      { question: 'What is this?', answer: 'This is a test.', timestamp: new Date() },
      { question: 'How does it work?', answer: 'It works well.', timestamp: new Date() }
    ];

    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    const messages = compiled.querySelectorAll('app-message');

    expect(messages.length).toBe(2);
  });

  it('should append new Q&A pair to conversation on successful response', () => {
    const chatService = TestBed.inject(ChatService);
    spyOn(chatService, 'sendQuestion').and.returnValue(
      of({ answer: 'Test answer', sources: [] })
    );

    component.question = 'Test question';
    component.onSubmit();

    expect(component.conversation.length).toBe(1);
    expect(component.conversation[0].question).toBe('Test question');
    expect(component.conversation[0].answer).toBe('Test answer');
    expect(component.question).toBe('');
  });

  it('should display loading spinner while query is in flight', () => {
    component.isLoading = true;
    fixture.detectChanges();

    const compiled = fixture.nativeElement as HTMLElement;
    const spinner = compiled.querySelector('.chat-spinner');

    expect(spinner).toBeTruthy();
    expect(spinner?.textContent).toContain('Thinking');
  });
});
