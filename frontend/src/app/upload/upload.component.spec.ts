import { TestBed } from '@angular/core/testing';
import { UploadComponent } from './upload.component';
import { provideHttpClient } from '@angular/common/http';

function makeFile(name: string, type: string, sizeBytes: number): File {
  const content = new Uint8Array(sizeBytes);
  return new File([content], name, { type });
}

describe('UploadComponent file validation', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [UploadComponent],
      providers: [provideHttpClient()],
    }).compileComponents();
  });

  it('should accept a valid PDF file', () => {
    const fixture = TestBed.createComponent(UploadComponent);
    const comp = fixture.componentInstance;
    const file = makeFile('test.pdf', 'application/pdf', 1024);

    comp.validateAndSetFile(file);

    expect(comp.selectedFile).toBe(file);
    expect(comp.errorMessage).toBe('');
  });

  it('should accept a valid TXT file', () => {
    const fixture = TestBed.createComponent(UploadComponent);
    const comp = fixture.componentInstance;
    const file = makeFile('notes.txt', 'text/plain', 512);

    comp.validateAndSetFile(file);

    expect(comp.selectedFile).toBe(file);
    expect(comp.errorMessage).toBe('');
  });

  it('should reject an unsupported file type', () => {
    const fixture = TestBed.createComponent(UploadComponent);
    const comp = fixture.componentInstance;
    const file = makeFile('image.png', 'image/png', 1024);

    comp.validateAndSetFile(file);

    expect(comp.selectedFile).toBeNull();
    expect(comp.errorMessage).toContain('Unsupported file type');
  });

  it('should reject a file exceeding 20 MB', () => {
    const fixture = TestBed.createComponent(UploadComponent);
    const comp = fixture.componentInstance;
    const twentyOneMB = 21 * 1024 * 1024;
    const file = makeFile('big.pdf', 'application/pdf', twentyOneMB);

    comp.validateAndSetFile(file);

    expect(comp.selectedFile).toBeNull();
    expect(comp.errorMessage).toContain('20 MB');
  });
});
