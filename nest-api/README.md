# NestJS API (Next-Phase Backend)

This folder provides a NestJS backend for the web-rebuild phase.

## What it exposes
- `POST /api/ets/analyze`
  - multipart field: `workbook` (single `.xlsx`)
  - optional form fields:
    - `selectedScenario`, `customEuaPrice`, `basePrice`, `stressPrice`, `highPrice`
    - `scope3FactorTco2PerT` (optional Scope 3 proxy override; default can come from `Factors` sheet)
    - `freeAllocationTco2` (planning approximation for net EUA requirement)
    - `measureReductionPct`, `measureAnnualizedCostEur` (break-even indicator inputs)
- `POST /api/ets/portfolio`
  - multipart field: `workbooks` (multiple `.xlsx`)
  - optional form fields: same as `analyze` plus `amberThresholdEur`, `redThresholdEur`
- `POST /api/ets/report`
  - multipart field: `workbook` (single `.xlsx`)
  - optional form fields: same scenario/assumption fields as `analyze` plus `reportOwner`
  - returns: PDF management report (`application/pdf`)

## Start
```bash
cd nest-api
npm install
npm run start:dev
```

Server runs on `http://localhost:4000` with global prefix `/api`.

## Why this exists
- Keeps ETS calculation logic available behind an API for a future web frontend.
- Supports both single-site and portfolio workflows.
- Lets you evolve to a full client app while preserving the current engineering method.
