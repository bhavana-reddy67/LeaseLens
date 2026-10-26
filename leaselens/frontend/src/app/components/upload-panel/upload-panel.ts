import { ChangeDetectionStrategy, Component, ElementRef, input, model, output, signal, viewChild } from '@angular/core';

import { DOCUMENT_CATEGORIES, DocumentCategory } from '../../models';
import { formatBytes } from '../../report-format';

const ALLOWED_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png'];

/** Client-side check for a quick message. The server validates again (type, signature, size). */
export function validateFile(file: File, maxMb: number): string | null {
  const extension = file.name.includes('.') ? file.name.split('.').pop()!.toLowerCase() : '';
  if (!ALLOWED_EXTENSIONS.includes(extension)) {
    return 'Unsupported file type. Please choose a PDF, JPG, JPEG or PNG file.';
  }
  if (file.size === 0) {
    return 'The file is empty.';
  }
  if (file.size > maxMb * 1024 * 1024) {
    return `The file is ${formatBytes(file.size)}, which is over the ${maxMb} MB limit.`;
  }
  return null;
}

@Component({
  selector: 'app-upload-panel',
  templateUrl: './upload-panel.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class UploadPanel {
  readonly maxMb = input(10);
  readonly busy = input(false);
  readonly extracted = input(false);
  readonly serverError = input<string | null>(null);

  readonly category = model<DocumentCategory>('rental');
  readonly file = model<File | null>(null);

  readonly extract = output<File>();
  readonly cleared = output<void>();

  readonly categories = DOCUMENT_CATEGORIES;
  readonly dragOver = signal(false);
  readonly validationError = signal<string | null>(null);
  readonly formatBytes = formatBytes;

  private readonly fileInput = viewChild.required<ElementRef<HTMLInputElement>>('fileInput');

  openPicker(): void {
    this.fileInput().nativeElement.click();
  }

  onPick(event: Event): void {
    const target = event.target as HTMLInputElement;
    const picked = target.files?.item(0) ?? null;
    if (picked) {
      this.accept(picked);
    }
    target.value = ''; // allow choosing the same file again
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    if (!this.busy()) {
      this.dragOver.set(true);
    }
  }

  onDragLeave(): void {
    this.dragOver.set(false);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragOver.set(false);
    if (this.busy()) {
      return;
    }
    const dropped = event.dataTransfer?.files.item(0) ?? null;
    if (dropped) {
      this.accept(dropped);
    }
  }

  onCategoryChange(event: Event): void {
    this.category.set((event.target as HTMLSelectElement).value as DocumentCategory);
  }

  remove(): void {
    this.file.set(null);
    this.validationError.set(null);
    this.cleared.emit();
  }

  startExtraction(): void {
    const current = this.file();
    if (current && !this.validationError()) {
      this.extract.emit(current);
    }
  }

  private accept(candidate: File): void {
    const problem = validateFile(candidate, this.maxMb());
    this.validationError.set(problem);
    if (problem) {
      return;
    }
    this.file.set(candidate);
    this.cleared.emit(); // a new file invalidates earlier extraction and analysis
  }
}
