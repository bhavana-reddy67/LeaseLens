import { ChangeDetectionStrategy, Component, computed, input, model, output } from '@angular/core';

import { ProviderName, ProvidersResponse, ProviderStatus } from '../../models';

@Component({
  selector: 'app-provider-panel',
  templateUrl: './provider-panel.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProviderPanel {
  readonly info = input<ProvidersResponse | null>(null);
  readonly loading = input(false);
  readonly error = input<string | null>(null);
  readonly disabled = input(false);

  readonly selected = model<ProviderName>('ollama');
  readonly cloudConsent = model(false);

  readonly refresh = output<void>();

  readonly selectedStatus = computed<ProviderStatus | null>(
    () => this.info()?.providers.find((p) => p.name === this.selected()) ?? null,
  );

  select(name: ProviderName): void {
    if (name !== this.selected()) {
      this.selected.set(name);
      // Consent is never carried over: it must be given again for the cloud provider.
      this.cloudConsent.set(false);
    }
  }

  onConsentChange(event: Event): void {
    this.cloudConsent.set((event.target as HTMLInputElement).checked);
  }

  statusLabel(provider: ProviderStatus): string {
    if (provider.available) {
      return 'Available';
    }
    return provider.configured ? 'Unavailable' : 'Not configured';
  }
}
