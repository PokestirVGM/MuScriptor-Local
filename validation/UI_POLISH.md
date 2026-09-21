# RC1 interface polish — 2026-09-21

The shared source and local release artifacts include the following changes:

- Native Mac/Windows headers use the official MuScriptor mark, wordmark, and Pokestir credit. The PNG renderer preserves SVG masks and nested noteheads; both themes have matching assets. The web header removes the LOCAL badge and decorative background glow.
- Gear menus collect session actions and app information. Desktop menus also expose processor selection, the model download folder, export checks, dependency repair, and logs. Browser information shows version and runtime details; processor changes happen through the desktop app after returning from the GUI.
- Open Web GUI has an outward arrow. Timing selectors have adequate widths, and detailed timing corrections use clearer labels and examples.
- Both desktop instrument lists have a bounded drag grip. Mac uses a fixed coordinate space to prevent drag feedback as the grip moves; Windows uses global pointer positions and supports keyboard adjustment.
- Mac windows support edge/corner resizing and remembered geometry. Windows retains its resizable main window.
- Mac has File, Edit, View, Window, and Help menus, standard open/save/settings shortcuts, and context-sensitive disabling while busy or showing a sheet.

## Checks

- Final Python run: **110 tests, successful, one optional hardware check skipped** (109 executed). This run enables the normally optional Windows visual-state checks; it includes native Qt event tests for drag distance, release, bounds, keyboard resizing, session-menu dispatch, and busy processor controls.
- Windows UI rendered and reviewed on the macOS-hosted offscreen Qt backend in both themes. Logo and gear contrast were corrected after review. These checks do not replace Windows hardware/scaling/installer testing.
- TypeScript checking and production web build passed. Existing bundle-size advisory remains.
- Mac release build compiled and ad-hoc signature verified. An isolated UI fixture showed the corrected complete logo, new header, drag-height change, menu-bar sections, and context-sensitive File actions. Its window is resizable. The fixture intentionally has no transcription engine and is not packaged.
- Browser checked at a narrow viewport: clean header, gear actions, version/runtime/model-folder dialog, and updated Pokestir tab title.
- The development app's real worker launch stalled in macOS dyld before Python initialized during this UI session. The same engine passed command-line regression tests. This is an unresolved development-launch verification limit; no new full native transcription claim is made by these UI checks.

The timing algorithm and prior accuracy limitations are unchanged. See RHYTHM_REFINEMENT.md and WINDOWS_HANDOFF.md for remaining release work. The source handoff includes the engine/frontend patch; no recordings, credentials, models, or test-preview applications are included.
