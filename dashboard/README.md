# dashboard

Static dashboard for the CryptoCadence paper track record (Vite + TypeScript,
no chart libraries — the equity curve is inline SVG).

Views:

- Equity curve (from the committed `journal/decisions.jsonl`)
- Total return / max drawdown / decision count
- Latest target weights, submitted orders and risk vetoes
- Full decision log

`scripts/copy-journal.mjs` copies the committed journal into `public/` before
every build, so the site ships the exact same tamper-evident data that is in git.

```bash
pnpm install
pnpm build     # tsc --noEmit && vite build -> dist/
pnpm dev       # local dev server
```

Deployed as a static site (GitHub Pages).
