import { TestBed, ComponentFixture } from '@angular/core/testing';
import { ChatComponent } from './chat.component';
import { ChatService } from '../shared/services/chat.service';
import { provideHttpClient } from '@angular/common/http';

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
      { question: 'What is this?', answer: 'This is a test.' },
      { question: 'How does it work?', answer: 'It works well.' }
    ];

    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    const messages = compiled.querySelectorAll('app-message');

    expect(messages.length).toBe(2);
  });

  it('should stream an answer into a new Q&A pair', async () => {
    const chatService = TestBed.inject(ChatService);
    async function* chunks() { yield 'Test'; yield ' answer'; }
    spyOn(chatService, 'streamAnswer').and.resolveTo({ sources: ['a.pdf'], chunks: chunks() });

    component.question = 'Test question';
    component.onSubmit();
    expect(component.question).toBe('');
    await fixture.whenStable();
    await new Promise((resolve) => setTimeout(resolve));

    expect(component.conversation.length).toBe(1);
    expect(component.conversation[0].question).toBe('Test question');
    expect(component.conversation[0].answer).toBe('Test answer');
    expect(component.conversation[0].sources).toEqual(['a.pdf']);
    expect(component.isLoading).toBeFalse();
  });

  it('should continue from the last whole word when a dial moves mid-answer', async () => {
    const chatService = TestBed.inject(ChatService);
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    async function* first() { yield 'The cell divi'; await gate; }
    async function* second() { yield 'divides fast.'; }
    const spy = spyOn(chatService, 'streamAnswer').and.returnValues(
      Promise.resolve({ sources: [], chunks: first() }),
      Promise.resolve({ sources: [], chunks: second() }),
    );

    component.question = 'Q';
    component.onSubmit();
    await new Promise((resolve) => setTimeout(resolve));

    component.onSteer({ ...component.steering, depth: 95 });
    release();
    await new Promise((resolve) => setTimeout(resolve, 10));

    expect(spy.calls.argsFor(1)[0].partialAnswer).toBe('The cell');
    expect(spy.calls.argsFor(1)[0].steering['depth']).toBe(95);
    const msg = component.conversation[0];
    expect(msg.answer).toBe('The cell divides fast.');
    expect(msg.segments?.[1].label).toBe('depth: thorough 90%');
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
