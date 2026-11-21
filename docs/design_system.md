# Design System — Clocktower Console & Field Manual

Scoped styling specification derived from **Chart Room (`BRAND.md` v2.2)** and implemented in `styles.css` (Tailwind v4 `@theme inline` + custom `@utility` hardware classes).

---

## 1. Visual Architecture & Aesthetic

* **Theme & Mode:** Dark mode by default (`#16181B` steel ground), pairing a **machined cast-steel & brass control console** with a **warm parchment field manual** (`#EDE4D2` / `#E5DAC3`).
* **Materiality:** Surfaces mimic physical hardware—machined 1px edges, brushed grain, recessed instrument cutouts, anodized rivets/bolts, and curved phosphor CRT glass.
* **Color Guardrails:**
  * No pure black (`#000000`) or pure white (`#FFFFFF`). Deepest ground is `--color-steel-950` (`#0F1114`); brightest ink is `--color-ink-050` (`#EDE6D6`).
  * **Alarm (`#B4544C`):** Reserved strictly for error chrome, rules, and badges—never used for body text.
  * Every state uses a glyph, rule, or text label alongside color.

---

## 2. Active Color & Typography Tokens

### Fonts (`@theme inline`)
* **UI, Labels, Console & Telemetry (`--font-mono`, default body):** `"IBM Plex Mono", "JetBrains Mono", ui-monospace, "Courier New", monospace`
* **Field Manual Prose & Headings (`--font-serif`):** `"Spectral", "Source Serif 4", Georgia, serif`

### Core Surfaces & Semantic Tokens (`:root`)
| Token | Hex | Role |
|---|---|---|
| `--background` | `#16181B` (`steel-900`) | App shell background |
| `--card` | `#1D2024` (`steel-800`) | Elevated panels & housings |
| `--popover` | `#24282D` (`steel-700`) | Popovers & overlays |
| `--foreground` | `#C6BEB0` (`ink-100`) | Default body text |
| `--muted-foreground` | `#8C8779` (`ink-300`) | Secondary labels & metadata |
| `--primary` | `#B99A63` (`brass-500`) | Primary brass hardware & accents |
| `--primary-foreground` | `#1A1512` (`teak-950`) | Engraved text on brass plates |
| `--secondary` | `#1B3322` (`forest-800`) | Structural grouping / active selection |
| `--accent` | `#2E4A5C` (`harbor-800`) | Informational chrome |
| `--destructive` | `#B4544C` (`alarm-500`) | Error borders, rules & badges |
| `--border` | `#333A41` | Default 1px hairline border |
| `--ring` | `#96763F` (`brass-700`) | `2px` focus-visible outline (`offset: 2px`) |

### Hardware & Weathering Palette (`--color-*`)
* **Steel:** `950 #0F1114` · `900 #16181B` · `800 #1D2024` · `700 #24282D` · `600 #2E333A` · `500 #3A4048` · `400 #4A4F57` · `200 #6C737E`
* **Brass:** `900 #4A3C20` · `800 #6E5A34` · `700 #96763F` · `500 #B99A63` · `400 #C7a362` · `300 #E3CB92`
* **Paper & Ink (Field Manual):** `paper-300 #F2EBDC` → `paper-800 #A8977A` · `ink-050 #EDE6D6` → `ink-950 #221C17`
* **Teak (Binder Spine):** `950 #1A1512` → `600 #6B4E37`
* **CRT & Signals:** `--color-phosphor` (`#5C9B6E`), `--color-phosphor-dim` (`#3D7248`), `--color-phosphor-ground` (`#0D1A12`), `--color-fathom` (`#35608A`), `--color-warn` (`#D2BD7A`), `--color-alarm` (`#B4544C`), `--color-alarm-bg` (`#2A1614`)
* **Patina / Wear Accents:** `--color-verdigris` (`oklch(0.39 0.045 163)`), `--color-oxide` (`oklch(0.33 0.025 65)`), `--color-dust` (`oklch(0.57 0.025 85)`), `--color-foxing` (`oklch(0.43 0.055 69)`)

---

## 3. Component & Hardware Classes (`styles.css`)

### Console Chassis & Housings
* `.faceplate` / `.aged-console`: Main cast-steel enclosure (`5px` border, machined vertical/horizontal grain lines, `1px` top specular edge, `4px` bottom drop). Wear layers stay in `::before` (`z-index: 0`) beneath interactive controls (`z-index: 1`).
* `.bolt`: `14px` circular slotted corner rivets (`::before` rotated `-35deg`).
* `.nameplate`: Engraved brass plate (`brass-700` to `brass-800`) with `teak-950` text and subtle verdigris/oxide patina.
* `.rubbed-lettering`: Worn silkscreen label effect via `background-clip: text`.
* `.recess` / `.gauge-deck` / `.control-cutout`: Sunken `steel-900`/`950` instrument bays with top machined seam lines (`::before`).

### CRT Display & Gauges
* `.crt-bezel` & `.crt-glass`: Sunken `18px / 14px` curved viewport over a radial `--color-phosphor-ground` gradient, layered with horizontal scanlines (`::after`) and subtle phosphor vignette/dust (`::before`).
* `.phosphor`: Glowing `#5C9B6E` CRT readout text (`text-shadow` at 30% alpha).
* `.trace-row`: 3-column waterfall grid (`minmax(0, 42%) minmax(0, 1fr) 7ch`).
* `.gauge-bezel` & `.gauge-dial`: `96px × 96px` circular steel/brass gauge housing (scales down to `80px` ≤1100px, `76px` mobile, `64px`/`44px` on short viewports).

### Tactile Controls
* `.mech-btn` / `.mech-btn-brass` / `.step-switch`: Physical push-buttons with a `4px` bottom lip that depresses (`translateY(4px)`) on `:active:not(:disabled)`.
* `.rocker-housing`, `.rocker-slot`, `.toggle-handle`, `.rocker-grip`: Vertical toggle switch assembly with ribbed brass handle.
* `.selector-assembly`, `.drum-bezel`, `.target-drum`, `.drum-lettering`: Mechanical rotary target drum (`40px 1fr 40px` grid) with `drum-step` (`140ms ease-out`) vertical roll animation.
* `.vertical-track`, `.vertical-lever`, `.stamped-notch`, `.major-notch`: Vertical range slider (`writing-mode: vertical-lr; direction: rtl`) with a brass thumb and stamped tick marks. (Horizontal variant: `.lever`).

### Field Manual
* `.parchment`: Warm `paper-400` to `paper-500` gradient sheet with `ink-700` prose and inner edge shading.
* `.binder-spine` & `.binder-ring`: `teak-900`/`700` spine paired with `22px × 12px` brass binder rings.

---

## 4. Responsive Breakpoints & Accessibility

* **Layout Ceiling:** `.workspace-panels` caps height at `900px`.
* **Breakpoints:**
  * `≤ 1100px`: Tightens `.aged-console` padding (`18px`) and shrinks `.gauge-dial` to `80px`.
  * `≤ 767px` (Mobile): Stacks `.screen-controls` into a `55px` side column, compacts `.mode-switch` and `.crt-glass` padding (`10px`), and adjusts `.trace-row` to `40% / 1fr / 7ch`.
  * `max-height: 700px` & `max-height: 500px` (landscape/short screens): Compresses vertical padding, `.target-drum` height (`30px`), `.action-deck` button height (`30px`), and `.gauge-dial` (`64px` / `44px`).
* **Reduced Motion:** `@media (prefers-reduced-motion: reduce)` forces `0ms` transition and animation durations globally.