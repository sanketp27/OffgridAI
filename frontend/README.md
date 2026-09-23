# OffgridAI Frontend

Next.js 16 · React 19 · TypeScript · Tailwind v4

## Run

```bash
cd frontend
nvm use 22   # Node 20.9+ required
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## 90-second demo script

1. **Storefront** `/` — tap **Vague hiking intent** (or type `waterproof hiking boots under 4000`)
2. See **Rescued** near-match banner → **Choose** TrailGrip → answer fit-check (**Size up to 9.5**) → bag updates
3. Optional: **Need it today** → stockout rescue → **Accept** an option
4. **Merchant** `/merchant` — session ribbon should show → **Generate Insights** → revenue-at-risk briefs
5. **Associate** `/associate` — upload any photo + order id → Analyze → Confirm disposition

## Surfaces

| Route | Role |
| --- | --- |
| `/` | Shopper — discovery, near-match, fit-check, stockout rescue |
| `/merchant` | Generate Insights — closed loop |
| `/associate` | Return-to-value — confirm / override |

## Live backend

```bash
# .env.local
NEXT_PUBLIC_USE_MOCK_API=false
NEXT_PUBLIC_API_BASE_URL=https://YOUR_CLOUD_RUN_URL
```

## Design

- Tokens: `design/tokens/`
- Philosophy: `docs/frontend/design_philosophy.md`
- Product art: `public/products/`
