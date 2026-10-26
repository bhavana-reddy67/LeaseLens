import { TestBed } from '@angular/core/testing';

import { UploadPanel, validateFile } from './upload-panel';

describe('validateFile', () => {
  it('accepts supported files within the limit', () => {
    expect(validateFile(new File(['x'], 'lease.PDF'), 10)).toBeNull();
    expect(validateFile(new File(['x'], 'scan.jpeg'), 10)).toBeNull();
  });

  it('rejects other types, empty files and large files', () => {
    expect(validateFile(new File(['x'], 'notes.docx'), 10)).toContain('Unsupported');
    expect(validateFile(new File([], 'empty.pdf'), 10)).toContain('empty');
    expect(validateFile(new File([new Uint8Array(2 * 1024 * 1024)], 'big.pdf'), 1)).toContain('over the 1 MB limit');
  });
});

describe('UploadPanel', () => {
  it('shows file details and emits the file for extraction', async () => {
    await TestBed.configureTestingModule({ imports: [UploadPanel] }).compileComponents();
    const fixture = TestBed.createComponent(UploadPanel);
    const panel = fixture.componentInstance;
    const emitted: File[] = [];
    panel.extract.subscribe((f) => emitted.push(f));

    const file = new File(['%PDF-'], 'lease.pdf', { type: 'application/pdf' });
    panel.file.set(file);
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;
    expect(element.textContent).toContain('lease.pdf');
    expect(element.textContent).toContain('Ready to extract');

    panel.startExtraction();
    expect(emitted).toEqual([file]);

    panel.remove();
    expect(panel.file()).toBeNull();
  });
});
