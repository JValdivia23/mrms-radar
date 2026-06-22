## Variant: Windy-style Floating Controls

### Design stance
Map-first with minimal, transparent chrome. Controls float over the image and auto-hide — the radar data is the entire experience, not framed by UI.

### Key choices
- **Layout:** Full-screen map, no borders, no chrome
- **Controls:** Floating glass-morphism panels (top bar, side drawer, bottom time scrubber, right zoom buttons)
- **Typography:** System font stack, 14px labels, glass backdrops
- **Color:** Dark transparent panels over radar imagery, blue accent
- **Interaction:** Auto-hiding top bar (4s timeout), hamburger slide-out panel, pinch-zoom + drag-pan via CSS transforms

### Trade-offs
- **Strong at:** Immersion — feels like a professional weather tool. Works identically on mobile and desktop. Zero learning curve for windy.com users.
- **Weak at:** The side panel covers the map when open (no simultaneous view+control). Time controls are minimal (step buttons, no full timeline).

### Best for
- Meteorologists and weather enthusiasts who want maximum map real estate
- Mobile-first usage where screen space is precious
- Users familiar with windy.com / radarscope interaction patterns
