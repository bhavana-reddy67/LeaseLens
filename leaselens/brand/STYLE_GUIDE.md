# LeaseLens Style Guide (PLACEHOLDER)

> **Placeholder notice.** The project brief asked for the supplied `brand/template.html`,
> `brand/theme.css` and `brand/STYLE_GUIDE.md`. They were not available when this project was
> created, so these three files are a minimal stand-in. **Replace all three with the official
> brand files.** The app imports `brand/theme.css` from one place (`frontend/src/styles.css`),
> so swapping the file restyles the whole UI. If the official theme uses different token or
> class names, update `frontend/src/styles.css` to map them.

## Principles

- Calm and trustworthy: this is a legal-tech tool people use before signing something important.
- Clarity over decoration: no unnecessary animation, no stock imagery.
- Risk colours carry meaning: use them only for risk levels, and always pair a colour with a text label.

## Layout

- Use the structure in `template.html`: `.site-header`, `main.site-main > .container`, `.site-footer`.
- Content width: `--max-width` (1120px). Side padding: `--space-4` on mobile, `--space-6` on desktop.
- Group content in `.card` blocks separated by `--space-6`.

## Typography

- Font: `--font-sans` (system UI stack). Monospace (`--font-mono`) only for extracted document text.
- Headings: h1 1.75rem, h2 1.25rem, h3 1.05rem, all weight 650.
- Body text: 1rem, line height 1.6. Muted text uses `--color-text-muted`.

## Colour tokens

| Token | Use |
|---|---|
| `--brand-primary` | Header, primary buttons, links |
| `--brand-accent` | Focus rings, selected states |
| `--color-bg` / `--color-surface` | Page background / cards |
| `--color-border` | Card and input borders |
| `--risk-high`, `--risk-medium`, `--risk-low`, `--risk-uncertain` | Risk badges only (with `-bg` variants) |

Dark mode is handled with `prefers-color-scheme` in `theme.css`.

## Components

- Buttons: `.btn` plus `.btn--primary` (one per section), `.btn--secondary`, `.btn--ghost`, `.btn--small`.
- Badges: `.badge` plus `.badge--high|medium|low|uncertain`.
- Alerts: `.alert` plus `.alert--info|success|warning|error`, with `role="status"` or `role="alert"`.
- Forms: wrap each control in `.field` with a visible `<label>`.

## Accessibility

- Text contrast at least 4.5:1. Never use colour as the only signal.
- Every control has a visible label; focus is always visible (`:focus-visible` ring).
- Status changes are announced with `aria-live`.
