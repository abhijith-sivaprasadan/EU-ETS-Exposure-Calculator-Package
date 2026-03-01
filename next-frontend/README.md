# Next.js Frontend (Phase 1 UI Rebuild)

Animated frontend for the NestJS EU ETS API.

## Run
```bash
cd next-frontend
npm install
npm run dev
```

Default URL: `http://localhost:3000`

Set API base if needed:
```bash
# Windows PowerShell
$env:NEXT_PUBLIC_API_BASE_URL="http://localhost:4000/api"
npm run dev
```

## Features included
- Single-site workbook analysis screen
- Portfolio multi-workbook planning screen
- Animated UI sections (Framer Motion)
- Neon dark theme + chart views
- Scenario and planning-case controls
- Guardrail-aware portfolio summary
