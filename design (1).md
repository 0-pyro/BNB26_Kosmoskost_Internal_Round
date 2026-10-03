# Design Specification --- Light Theme Color Change Only

## CRITICAL INSTRUCTION

This document authorizes **ONE AND ONLY ONE type of change** to the
existing website:

> **Change the website's colors to the specified light-theme color
> palette.**

**Do not change anything else.**

The existing website must remain functionally, structurally, visually,
and behaviorally identical except for the color palette.

------------------------------------------------------------------------

## 1. Target Dark Theme Palette

Use ONLY these four colors as the new light-theme palette:

  Color         Hex
  ------------- -----------
  Dark Navy Blue   `#0C134F`
  Royal Blue    `#1D267D`
  Purple    `#5C469C`
  Light Lavender      `#D4ADFC`

These are the exact colors requested. Do not replace them with similar
shades, gradients, automatically generated shades, or alternative
colors.

------------------------------------------------------------------------

## 2. What You ARE Allowed To Change

You may modify **only color-related styling** required to apply the
palette above.

This includes, where applicable:

-   Background colors
-   Section/container background colors
-   Card backgrounds
-   Header/navigation backgrounds
-   Sidebar backgrounds
-   Buttons and button backgrounds
-   Borders
-   Input backgrounds
-   Input borders
-   Accent colors
-   Icons
-   Decorative elements
-   Hover colors
-   Active/selected colors
-   Focus colors
-   Status colors **only if necessary to fit the new theme without
    changing their meaning**
-   Existing CSS variables/theme tokens
-   Existing Tailwind color classes or equivalent color declarations

The purpose is to make the existing website consistently use the four
provided colors for its **light theme**.

------------------------------------------------------------------------

## 3. What MUST NOT Be Changed

### Absolutely do NOT change:

-   Page layout
-   Component structure
-   HTML/JSX structure
-   React component logic
-   JavaScript/TypeScript logic
-   API calls
-   Backend code
-   WebSocket behavior
-   Routing
-   Navigation flow
-   Authentication
-   State management
-   Database logic
-   Data
-   Text/content
-   Labels
-   Button names
-   Icons
-   Images
-   Logos
-   SVG shapes
-   Illustrations
-   Fonts
-   Font sizes
-   Font weights
-   Typography
-   Spacing
-   Padding
-   Margins
-   Widths
-   Heights
-   Border radius
-   Shadows
-   Animations
-   Transitions
-   Responsiveness
-   Breakpoints
-   Accessibility behavior
-   Form behavior
-   Validation
-   Loading states
-   Error handling
-   Dependencies
-   Package versions
-   Build configuration
-   Vite configuration
-   TypeScript configuration
-   File/folder structure

**Do not refactor code.**

**Do not clean up code.**

**Do not rename variables, components, files, classes, IDs, routes, or
functions.**

**Do not "improve" the UI while applying the colors.**

**Do not redesign anything.**

------------------------------------------------------------------------

## 4. Strict Visual Preservation Rule

Before making changes, inspect the existing website and understand its
current visual structure.

After the change:

> **Every element must remain in exactly the same position, size, shape,
> spacing, typography, and behavior as before.**

The only noticeable difference should be the **color palette**.

If a change is not required to change a color, **do not make that
change**.

------------------------------------------------------------------------

## 5. Color Application Guidance

Use the four colors thoughtfully within the existing design.

Suggested palette roles:

-   `#0C134F` --- primary dark/background surface
-   `#1D267D` --- secondary surface/card/section background
-   `#5C469C` --- borders, secondary surface, supporting UI
-   `#D4ADFC` --- strong accent, buttons, active states, or highlights

These role suggestions are guidance only. Preserve the existing
website's current hierarchy and component design.

Do **not** introduce additional colors just to make the palette work.

If text currently uses a color that is necessary for readability,
preserve readability while making the smallest possible color-only
adjustment. Do not alter typography or layout.

------------------------------------------------------------------------

## 6. No Gradient / No New Effects

Do not introduce:

-   New gradients
-   New glassmorphism
-   New shadows
-   New animations
-   New hover effects
-   New visual effects
-   New decorative elements

If gradients already exist, do not redesign them. Only adjust their
existing color values when necessary to apply the requested palette.

------------------------------------------------------------------------

## 7. Light Theme Only

This specification applies specifically to the **light theme**.

Do not modify or create a dark theme unless the existing implementation
requires a shared color token to be changed and doing so is unavoidable.

Do not add a theme switcher.

Do not change theme behavior.

------------------------------------------------------------------------

## 8. Implementation Rule

Prefer the **smallest possible code changes**.

If the project already uses:

-   CSS variables → update only the relevant color values.
-   Tailwind classes → change only the relevant color classes.
-   Theme tokens → update only the relevant color tokens.
-   Component-level styles → change only the color declarations.

Do not rewrite components unnecessarily.

------------------------------------------------------------------------

## 9. Verification Checklist

After making the color changes, verify:

-   [ ] Website still starts normally.
-   [ ] All existing pages/routes still work.
-   [ ] All buttons still work.
-   [ ] Forms still work.
-   [ ] Navigation still works.
-   [ ] WebSocket/API behavior is unchanged.
-   [ ] No console errors were introduced.
-   [ ] No dependencies were changed.
-   [ ] No files unrelated to styling were modified.
-   [ ] Layout is unchanged.
-   [ ] Typography is unchanged.
-   [ ] Spacing is unchanged.
-   [ ] Component sizes are unchanged.
-   [ ] Only colors have changed.
-   [ ] The light theme consistently uses the requested palette.

------------------------------------------------------------------------

## 10. Final Non-Negotiable Rule

### CHANGE COLORS ONLY.

If you are unsure whether a proposed change is allowed, **do not make
the change**.

Do not interpret this document as permission to improve, redesign,
refactor, optimize, modernize, simplify, reorganize, or otherwise modify
the website.

**The website must remain exactly the same except for its colors.**

### Required palette

``` text
#0C134F
#1D267D
#5C469C
#D4ADFC
```
