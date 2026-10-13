# Storefront React + TypeScript

Mobile-first storefront using React, React Router, TanStack Query and Vite. Flask continues to own authentication, CSRF, prices, quotes, order transactions, payments and downloads. Administration and private order pages retain native server forms.

Use Node 24 and pnpm 11.25.0:

```sh
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend test
pnpm --dir frontend build
python -m pytest -q
```

The build writes `app/static/storefront/` (ignored by Git). Flask embeds the initial public catalogue, cart, CSRF token and public settings in the existing HTML. React Router opens cached product pages without another HTML request. Query cache lives only in memory, expires and is never persisted to browser storage. Cart writes are optimistic, serialized, CSRF-protected and reconciled against the server; failed POSTs are never retried automatically. Checkout uses a server-generated key and quote; price changes require confirmation with the refreshed quote. Signed order/payment/download URLs use native navigation.

HTML routes still render meaningful titles, canonical links, descriptions, product metadata and a working fallback if JavaScript is unavailable. Drafts, digital file paths, operator email, payment credentials and bank instructions are excluded from public JSON. SPA analytics go through the same consent/DNT/GPC checks and deduplication as server-rendered visits.

CI tests and builds once, stamps the exact Git revision and uploads the generated assets as an artifact. The deploy job sends that artifact over the existing verified SSH connection; Alwaysdata does not need Node. Deployment validates the build revision and manifest, retains older hashed files for open tabs, updates the manifest, reloads uWSGI and verifies the React mount and public revision. Never edit generated assets on Alwaysdata.

Mobile navigation reserves bottom and safe-area space; forms use 16px inputs and controls at least 44px. Automated tests cover cached navigation, optimistic reconciliation/rollback, checkout contracts and quantity limits. A phone check remains necessary for actual device rendering and network conditions.
