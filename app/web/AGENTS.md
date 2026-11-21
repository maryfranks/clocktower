## Project rules
- All game data goes through src/api/clocktowerClient.ts, typed by src/api/types.ts mirroring openapi.yaml; VITE_USE_MOCK_API (default true) swaps in src/api/mockStage1.ts so the UI never knows which backend it hits.
- The client strips gauge.* span attributes before traces reach the UI.
- Console materials and wear live in global CSS; hardware controls use Button variants so themed finishes stay consistent.
- Keep the switchboard inside the viewport with a flexible CRT area; traces use a separate fixed duration column so bars cannot cover timings.
