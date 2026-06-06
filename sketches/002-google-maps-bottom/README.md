## Variant: Google Maps-style Bottom Sheet

### Design stance
Familiar, structured chrome. A persistent bottom sheet holds quick-access controls, and a search bar anchors the top. Feels instantly recognizable — it's the Google Maps pattern that billions of people already know.

### Key choices
- **Layout:** Map underneath, search bar fixed top, collapsible bottom sheet
- **Controls:** Product chips (horizontal scroll), time slider with step buttons, quick-action chips, separate overlay panel
- **Typography:** Google Sans feel via system fonts, 28px time display, chip-based selectors
- **Color:** Dark Material surfaces (#202124), Google-blue accent (#8ab4f8)
- **Interaction:** Bottom sheet drags up/down via handle, overlay slides up from bottom, pinch-zoom + drag-pan on map

### Trade-offs
- **Strong at:** Familiarity — anyone who's used Google Maps gets it instantly. Bottom sheet allows map + controls simultaneously. Chips are fast for product switching.
- **Weak at:** The bottom sheet covers ~20% of the screen even when collapsed (just the handle). Feels heavier than windy-style. The search bar is a promise we can't fully deliver (geocoding needs an API).

### Best for
- General users who've never seen a radar viewer before
- Desktop use where screen real estate isn't constrained
- Quick product switching (chips are faster than dropdowns)
