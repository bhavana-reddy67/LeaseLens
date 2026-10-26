import { AnalyzeResponse, DOCUMENT_CATEGORIES, Finding, RISK_LABELS } from './models';

/** Plain-text report for the clipboard. Built only from the analysis the server returned. */
export function formatReport(result: AnalyzeResponse, findings: Finding[], fileName: string | null): string {
  const category = DOCUMENT_CATEGORIES.find((c) => c.value === result.category)?.label ?? result.category;
  const lines: string[] = [
    'LeaseLens contract review',
    `Document: ${fileName ?? 'uploaded document'} (${category})`,
    `AI provider: ${result.provider} / ${result.model}${result.processed_locally ? ' (processed locally)' : ' (cloud)'}`,
    '',
    `Summary: ${result.summary.headline}`,
  ];

  if (result.warnings.length) {
    lines.push('', 'Notes:', ...result.warnings.map((w) => `- ${w}`));
  }

  findings.forEach((finding, index) => {
    lines.push(
      '',
      `${index + 1}. [${RISK_LABELS[finding.risk_level]}] ${finding.category_label}${finding.page ? ` (page ${finding.page})` : ''}`,
      `   Clause: "${finding.excerpt}"`,
      `   Why: ${finding.reason}`,
      `   Possible impact: ${finding.impact}`,
    );
    if (finding.questions.length) {
      lines.push('   Questions to ask:', ...finding.questions.map((q) => `   - ${q}`));
    }
    if (finding.references.length) {
      lines.push(`   General guidance: ${finding.references.map((r) => `${r.source_id} ${r.title}`).join('; ')}`);
    }
    if (finding.uncertainty_notes.length) {
      lines.push(`   Notes: ${finding.uncertainty_notes.join(' ')}`);
    }
  });

  lines.push('', result.disclaimer);
  return lines.join('\n');
}

export function formatEmail(subject: string, body: string): string {
  return `Subject: ${subject}\n\n${body}`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
