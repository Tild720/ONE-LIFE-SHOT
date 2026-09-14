# ONE-LIFE-SHOT — Unreal Engine workflow

## Project layout

- The Git root is this directory.
- The Unreal project is `One_life_Shot/One_life_Shot.uproject`.
- It targets Unreal Engine 5.8 and is currently Blueprint-only: there is no `Source/` directory.
- The current starter content includes the Third Person template and `Content/ThirdPerson/Lvl_ThirdPerson`. Inspect the Content Browser before creating, renaming, or replacing an asset.
- Read [the game design brief](docs/GAME_DESIGN.md) before changing gameplay, UI, enemies, weapons, or level flow.

## Working rules

- Inspect the current project structure and existing assets before working. Reuse existing classes, Blueprints, and assets; never invent an asset name or path.
- Implement only the requested feature. Keep the change small, leave functioning systems alone, and do not perform unsolicited refactors or feature work.
- Follow the existing naming convention and folder layout. Extract genuinely shared functionality for reuse rather than duplicating it.
- Expose gameplay tuning values to the Unreal Editor where practical.
- Choose C++ or Blueprint based on the existing project and the task; do not force either approach. Avoid unnecessary Tick work in favor of events, delegates, and timers.
- Treat `Content/` assets (`.uasset`, `.umap`) as editor-managed binary files. Do not edit, rename, move, or delete them from the filesystem. Make asset changes through Unreal Editor tools or explicitly approved automation, then verify the result in the editor.
- Keep generated folders out of commits: `Binaries/`, `Intermediate/`, `Saved/`, and `DerivedDataCache/` (including their plugin equivalents).
- Before changing project settings, plugins, maps, or assets, inspect the current configuration and explain the intended editor-visible effect.
- Keep Blueprint-facing names and public inputs stable unless the task explicitly includes a migration.
- Prefer small, verifiable changes. For gameplay or content work, validate in Play-In-Editor or with an applicable Automation Test when the editor is available.

## Game invariants

- Keep a fixed third-person quarter-view camera. The player aims with the mouse; aiming does not rotate the camera.
- A weapon provides one shot and has no reload. The core loop is `shoot → defeat an enemy → acquire that enemy's weapon → take the next shot`.
- Preserve distinct weapon roles: Pistol = single target; Shotgun = close-range multi-target; Sniper = long-range penetration; RPG = area explosion.
- Do not add a feature that interrupts or undermines the core weapon-acquisition loop. Treat weapon throwing, pickup slow motion, and combo as separately requested systems, not implicit additions.
- After implementation, report the changed files/assets and a concise verification method.

## Build and automation

- Use the engine version declared by the `.uproject`; do not silently switch engine versions.
- This repository has no C++ targets yet. Do not create a C++ module merely to make a small Blueprint or configuration change.
- When adding C++ is explicitly requested, generate project files first, then build the `One_life_ShotEditor` target with UnrealBuildTool and report the exact command and outcome.
- For packaging, use Unreal Automation Tool with an explicit platform and configuration. Do not package or publish builds unless requested.

## Unreal MCP

- UE 5.8 includes the experimental `ModelContextProtocol` plugin. Enable it together with `All Toolsets` only when editor control is requested.
- Keep its server loopback-only. The default endpoint is `http://127.0.0.1:8000/mcp`; never expose it to the network because it has no authentication layer.
- Let Unreal Editor generate the Codex client configuration after the plugins are enabled; do not overwrite an existing generated MCP configuration blindly.
