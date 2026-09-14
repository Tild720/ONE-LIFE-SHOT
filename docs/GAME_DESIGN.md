# ONE LIFE SHOT — Game Design Brief

## Product vision

ONE LIFE SHOT is a PC sci-fi action shooter set in a robot research and production facility. The player is a combat android escaping the facility by defeating robots and taking their weapons. A single bullet is both the player's attack opportunity and survival resource.

## Core loop

`Enter combat zone → identify enemies and their weapons → fire one shot → defeat an enemy → acquire its weapon → plan the next shot → clear the zone`

- Each acquired weapon has exactly one shot and cannot reload.
- A defeated enemy drops the weapon it used.
- The order in which enemies are defeated determines the available next weapon.
- On death, restart from the current combat zone/checkpoint.
- Encounters should feel like action puzzles: decide whom to defeat first and which weapon to carry into the next decision.

## Camera and player control

- Use a fixed third-person quarter-view camera.
- Aim with mouse direction without rotating the camera.
- Keep UI minimal and make the current one-shot state immediately readable.

## Weapon roles

| Weapon | Role | Intended use |
|---|---|---|
| Pistol | Single target | Reliable, accurate baseline weapon |
| Shotgun | Close-range multi-target | Clears clustered nearby enemies |
| Sniper | Long-range penetration | Solves distant or aligned threats |
| RPG | Area explosion | Clears groups through blast damage |

Do not make new weapons overlap these roles without an explicit design decision.

## Enemy roles

| Enemy | Weapon | Behavior goal |
|---|---|---|
| Basic combat robot | Pistol | Common baseline enemy and Pistol source |
| Assault robot | Shotgun | Pressures the player at close range |
| Heavy armored robot | RPG | Slow, high-impact area threat |
| Sniper robot | Sniper | Restricts movement from range |

## Combat and UI systems

Core UI: central crosshair, current weapon, emphasized ammo state (`1 / 0`), player state, combo count, stage progress, death, and fast restart.

The following are planned systems and should be implemented only when specifically requested:

- Throw an empty weapon to briefly interrupt an enemy.
- Brief pickup slow motion to read and aim at the next threat.
- Combo growth for quick consecutive eliminations.

## Stage progression

1. **Research Facility** — Pistol tutorial; small 1–3 enemy encounters teach the core loop.
2. **Robot Production Factory** — Introduces Shotgun; narrow machinery spaces emphasize close combat and quick pickup decisions.
3. **Security Zone** — Introduces Sniper; corridors and open spaces emphasize target order.
4. **Energy Core** — Introduces RPG; area damage enables multi-enemy solutions.
5. **Central Control Room** — Mixes all weapons and enemy types; the player solves the full target-order puzzle.

## Visual direction

Use a near-future robot facility: metal structures, neon lighting, holograms, and machinery. Differentiate research, production, security, and core spaces while preserving the sci-fi facility identity.

## Delivery checks

For each implemented gameplay feature, record the changed files/assets and a concise test path. Verify that the feature preserves the one-shot weapon-acquisition loop and does not duplicate existing content.
