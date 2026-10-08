# AgentGuard Design System: Money Map

## Visual Identity & Palette
- **Structural Colors (Navy / Neutral)**:
  - Deep Navy Canvas: `#0b111e`
  - Card Surface Navy: `#111a2e`
  - Elevated Card / Hover: `#18243e`
  - Subtle Borders & Dividers: `#233354`
  - Arrow Lines: `#334155` (default), `#60a5fa` (hover/focus highlight)
- **Risk Colors (Strictly Limited to Badges, Status Dots, HELD Stamp)**:
  - **Safe**: Emerald `#10b981` (Icon: `✓`, Word: `Safe`)
  - **Watch**: Amber `#f59e0b` (Icon: `👁`, Word: `Watch`)
  - **High Risk**: Crimson `#ef4444` (Icon: `⚠`, Word: `High risk`)
- **Structure Rule**: Only navy/neutral for all layout cards, background, and arrows. Risk colours appear ONLY on verdict badges, status dots, and the HELD stamp, always accompanied by both an icon and a text word. Exactly 3 risk states exist on screen.

## Typography
- **Body Font Size**: 18px body text throughout the interface.
- **Minimum Font Size**: 14px strictly enforced. Nothing on the screen is smaller than 14px.
- **Summary Headline**: 20px font directly above the Money Map for the executive summary sentence.
- **Monospace Elements**: 16px monospace for arrow labels, currency amounts, and account IDs.
- **Font Stack**: System UI Sans (`Inter`, `-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, `sans-serif`) and Monospace (`JetBrains Mono`, `ui-monospace`, `Menlo`, `monospace`).

## Money Map Columns
- **LEFT**: "Money came from" (Inbound senders, sorted by amount, max 5 visible + expand button, calm placeholder if empty)
- **CENTRE**: "This account" (Large focal card with name, small mono ID underneath, verdict badge, risk score ring, shared device chip)
- **RIGHT**: "Money went to" (Outbound payees, sorted by amount, max 5 visible + expand button, calm placeholder if empty)

## Legends & Guidance
- Standard 3-item legend:
  - `● Safe` (Emerald)
  - `● Watch` (Amber)
  - `● High risk` (Red)
- Clarifying guidance note:
  - "Arrow thickness = amount."

## Accessibility & Responsiveness
- **Keyboard Navigation**: All person cards are focusable (`tabIndex={0}`) and activated with `Enter`.
- **Reduced Motion**: Full support for `prefers-reduced-motion` with all animations disabled.
- **Responsive Layout**: Fluid column grids that adapt smoothly across 1440px, 1100px, 768px, and 390px (mobile) with zero horizontal overflow and no clipped text.
- **Accessible Table View**: Quick "Map | Table" toggle rendering equivalent tabular data for screen readers and printing.
