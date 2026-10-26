import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';

import { EXTRACTION_METHOD_LABELS, ExtractionResponse, PageText } from '../../models';

@Component({
  selector: 'app-text-review',
  imports: [DecimalPipe],
  templateUrl: './text-review.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TextReview {
  readonly extraction = input.required<ExtractionResponse>();
  readonly pages = input.required<PageText[]>();
  readonly disabled = input(false);

  readonly pageEdited = output<{ page: number; text: string }>();
  readonly resetEdits = output<void>();

  readonly methodLabels = EXTRACTION_METHOD_LABELS;
  readonly editedChars = computed(() => this.pages().reduce((sum, p) => sum + p.text.trim().length, 0));
  readonly isEdited = computed(() =>
    this.pages().some((page, index) => page.text !== this.extraction().pages[index]?.text),
  );

  onEdit(page: number, event: Event): void {
    this.pageEdited.emit({ page, text: (event.target as HTMLTextAreaElement).value });
  }
}
