# Runner progress HUD

## Assets

- `Content/UI/WBP_RunnerProgress`: top-centered route progress HUD.
- `Content/Runner/BP_RunnerProgress`: creates the HUD at BeginPlay and removes it at EndPlay. Existing route/stage calculations remain the source of truth.

## Behavior

- Shows start-to-end progress as a cyan horizontal track, moving runner icon, finish flag and integer percentage.
- Reads the existing manager's clamped `Progress` (0–1); it does not change stages, spawning, player movement or input mode.
- The runner travels 544 logical pixels. Display progress interpolates toward the real value; moving backward moves the icon backward as well.
- A 0.033333-second timer updates the display. Arms and legs swing while the player's horizontal velocity exceeds 10 cm/s; they stop when idle. Destruct clears the timer.
- Widgets are hit-test invisible, so the HUD does not capture mouse aiming or firing.

## Editing

Open `WBP_RunnerProgress` in the UMG Designer. The panel is centered at the top, with 640 × 88 logical size and 22-unit top margin. Change colors, font and shapes in Designer.

If changing the track width, also change the `544` travel multiplier in `UpdateHUD`, checkpoint positions and finish flag placement. Interpolation speed is `12`; limb swing and animation speed are in the same function. The UI uses native UMG shapes and the default engine font, with no external texture dependency.

## Test

Play `Lvl_ThirdPerson`. Walk from StartPoint toward EndPoint: percentage and runner should advance together. Walk backward: both should decrease. Stop: limb animation should stop. Verify 0%, 25%, 50%, 75%, 100%, and confirm normal mouse aim/fire beneath the HUD. Stop and restart PIE to check HUD lifetime.
