Learning lessons from my last project, I took a different approach with teh plan. instead of having the agent gnerate it based on my description, I generated a layout and then went step by step, always keeping in mind that v1 was a single puzzle that touched all of the microservices. I committed early so that when it generated new text, I could immediately see the diffs and caught some important sneaky changes before they became part of the app. I invested even more time in the planning stage for this app, first brainstorming the idea based on what I wanted the game to be, and then investing in the planning doc. I wanted to nail down how it all fit together before I started building.

I gave the agent the real life scenarios that I wanted to teach and we came up with the idea of the broken clocktower together. It then suggested the puzzles based on real things in a clocktower, which i thought was pretty cool. It suggested controls and we fined tuned the end state UI together.

I started with repo scaffolding and plenty of docs. the agent in my last project took some liberties with repo organization so I scaffolded it all out this time myself.



## Prompts:

### Frontend Generation

Build The Clock Tower, an observability puzzle game featuring a physical clocktower switchboard console paired with an external Engineer's Field Manual, using my attached brand document for colors and fonts and my attached openapi.yaml for all API types and mock responses.

Visual & Layout Rules
- Break away from standard web cards: Do not build flat 1px-bordered --card boxes, navbars, rounded pill buttons, or global serif body text.
- Switchboard Console (Diegetic Hardware): Render as a single machined instrument panel with beveled bezels, recessed CRT glass, bolted faceplate corners, tactile mechanical buttons, a notched 0-100 slider (step 5), PREV/NEXT target buttons, and three round analog dial gauges with animated needles (damped spring physics), each mounted above an engraved bronze nameplate (MAINS TENSION, RESONANCE DRAG, RESERVE PRESSURE) and featuring tick marks on the dial face with no readable numbers. Use uppercase --font-mono only on the console; keep the CRT strictly in-universe (no tutorials or real-world notes inside the screen).
- CRT Toggle: Physical switch flipping between Chamber View (live mechanical state/logs) and Trace View (last 5 trace waterfalls with expandable spans and attributes; strip any gauge.* keys).
- Control Deck: PREV/NEXT target selector, 0-100 slider (step 5), and four action buttons: PROBE, CALIBRATE, ENGAGE, RESET.
- Engineer's Field Manual (Printed Binder): Reserve --font-serif and warm parchment tones for the external manual with 3 tabs (How to Play, Stage Hints, Real-World Parallel). Auto-focus the manual at stage start and stage completion.
- Responsive Focus-Swap: Desktop shows both side-by-side and swaps scale on click/ESC (Focus Panel). Mobile stacks full-screen with a slim docked peek bar for the inactive view.

Decoupled API & Stage 1 Mock (VITE_USE_MOCK_API=true default)
- Implement src/api/clocktowerClient.ts strictly matching openapi.yaml (POST /api/session, POST /api/action, GET /api/traces/{session_id}), defaulting to relative /api paths when VITE_USE_MOCK_API=false.
- Include a complete local Stage 1 Mock ("Wake the Tower — Scale-to-Zero Cold Starts") matching openapi.yaml: targets (mainspring-drive, chime-regulator, escapement-gear, pendulum-cache) start cold (PROBE triggers ~2000ms trace with container.cold_start = true and spikes RESONANCE DRAG, warming that target to ~60ms); CALIBRATE (value: 75 on mainspring-drive once all targets are warm) stabilizes MAINS TENSION; ENGAGE verifies all targets are warm/calibrated and completes Stage 1; RESET resets state and traces.

