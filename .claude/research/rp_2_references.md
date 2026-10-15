# RP.2 Reference corpus census (Godot 4.x projects and addons)

Date 2026-10-15. Engine: Godot 4.7.stable.official.5b4e0cb0f. Scripts: `.claude/research/scripts/rp_2_census/`. Clones (shallow, depth 1, untrusted): `/tmp/claude-0/-home-user/77c17b82-ea72-5e78-90c8-1959b76a4dc3/scratchpad/dl/refs/<name>/` (names in the YAML below). Per-repo JSON, logs: `.../scratchpad/research/rp2_work/` (`census_<name>.json`, `log_<name>_{import,load}.txt`).

## Answer
1. 11 of the 13 named candidates exist and were cloned. Not found or not usable: **Kenney `Starter-Kit-2D-Platformer`** (git asks for credentials = no such repo; the 3D-Platformer, FPS, City-Builder and Racing kits exist), and **Cogito** is not on GitHub (`Phazorknight/Cogito` fails; the awesome-godot link is `codeberg.org/Phazorknight/Cogito` and clones fine). Celeste is C# and was only read, not loaded.
2. **Best copy-adapt sources (MIT/CC0, load clean on 4.7, typed):** `godot-demo-projects` (official, API usage), `Maaack/Godot-Game-Template` (flow/menus/pause/settings/audio), `godot-open-rpg` (GDQuest; camera, grid pathfinding, transitions, inventory, stat Resources), `phantom-camera`, `nezvers/Godot-GameTemplate` `addons/top_down` (components, damage, dash, projectiles; Resource-driven), `gloot` (inventory model), `beehave` and `godot-statecharts` (AI/state, both with test suites), `trauma-gd` (shake).
3. **Best complete GAMES for architecture:** `librerama` (GPL-3, design only; 2 autoloads, 183 scripts/scenes load with 0 errors, typed 1.00), `sourceofmana` (MIT code, art mixed; 455 files, 0 errors), `wutw` (CC0, 51k LOC, production roguelite; NOT loadable here: needs Wwise, Steam and a C++ GDExtension), `sunder` (AGPL, design only; GUT tests). `godot-open-rpg` is a demo/template, not a shipped game.
4. **Platformer-controller reality check (P01 is where agents fail first):** no vetted 4.x reference gives coyote + buffer + designer-intent jump (h, t_apex) cleanly. The official demo `2d/platformer` has neither coyote nor buffer. The two Asset Library controllers fail on quality: `Expandable-Platformer-Controller-2D` **does not compile on 4.7** [Run]; `Ultimate-Platformer-Controller-2D` adds gravity without `delta` and uses `await create_timer` for coyote/buffer [Src]. RP.A must write its own reference and use these only as parameter-naming inspiration. Celeste `Player.cs` (MIT, C#) is design reference only.
5. **Licence traps:** librerama, sunder, hurrycurry, reia (GPL-3 or AGPL-3) and supertuxparty (GPL-3): design-only, never copy code. `sourceofmana` is MIT for code only (art listed separately). Maaack's template saves progress as `user://global_state.tres` (see traps), which the P13 rule forbids.
6. Autoload counts (P11): good 2-3 (sunder 2, librerama 2, Maaack 3); questionable 8-13 (hurrycurry 8, open-rpg 9, wutw 12, tof2 13).

## Method (all [Run] unless tagged)
- Clone: `git clone --depth 1`; commit/date/remote from `git rev-parse HEAD`, `git log -1`. Licence: read the LICENSE file head and the README licence section.
- Godot version: `config/features` in `project.godot`, else README or `plugin.cfg` (addon-only repos have no project; marked).
- Load-check: copy the repo (no `.git`) to a throwaway dir, inject `res://__census/c.tscn` as main scene (autoload globals only exist when running a scene, NOT with `--script`; my first `--script` run gave false "Identifier not found: Audio" errors, discarded), run `godot --headless --path <copy> --import`, then `--quit-after 3000`. The injected script `ResourceLoader.load`s (cache ignored) and instantiates every `.gd` and `.tscn` with a Logger capture (`OS.add_logger`) and reports files with an ERROR (e) or WARNING (w). Exit codes were not trusted. Demos were checked as 16 selected sub-projects, not all 139.
- Godot-3 idiom grep: the 48 hand rules of `r1_5_failure_lint.md` (`rules.json`) minus 4 noisy ones, over `.gd/.tscn/.tres`. Hits were read; almost all are false positives (e.g. `emit_signal("x")` flagged as yield, `"None"` strings, `Gloot.instance()` singletons, vendored gdUnit4). Real Godot-3 residue: `format=2` `.tres` headers (tof2, wyvernbox 36 files, librerama 5, dialogic 6, gloot 1) and the two Godot-3 projects.
- Typed ratio = `var x:`/`var x :=` over all `var` declarations, and `->` over all `func`, on own-code roots (vendored addons excluded where known).
- Ratings 0-2 are MECHANICAL, from numbers I measured: typed 2 if var>=0.85 and ret>=0.85, 1 if var>=0.5, else 0. no-G3 2 = clean load and only explained hits; 1 = some G3 residue; 0 = Godot 3 project. tunables 2 = `@export`>=20/KLOC and >=1 Resource subclass; 1 = >=5/KLOC or a Resource; else 0. split 2 = `.tscn`/`.gd`>=0.5 and `add_child`<=10/KLOC; 1 = >=0.2 or otherwise partly; n/a for pure libraries. tests 2 = >=10 test files for own logic, 1 = 1-9, 0 = none. They measure shape, not whether the code is good.

## Ranked table (shortlist)
Columns: ratings T=typed, G=no-G3, U=tunables, S=scene/script split, X=tests. Load = errors/files checked (game+addon scripts and scenes) on 4.7.

| # | Repo @commit (date) | Licence | Godot | Load-check [Run] | T G U S X | Use |
|---|---|---|---|---|---|---|
| 1 | godot-demo-projects @b761b4c (2026-10-08) | MIT | 4.7 | 16 sub-projects, 0 errors (2 warn in `3d/kinematic_character`) | 2 2 1 2 0 | copy-adapt (API use) |
| 2 | Maaack/Godot-Game-Template @6849d6c (2026-09-10) | MIT | 4.7 | 0/244 | 1 2 2 2 0 | copy-adapt |
| 3 | gdquest-demos/godot-open-rpg @d59f2f7 (2026-10-13) | MIT code, assets CC0 per CREDITS.md | 4.7 (README: needs 4.7.2+; loaded on 4.7.0) | 0/122 own; 2/348 vendored dialogic editor files | 2 2 2 2 0 | copy-adapt |
| 4 | ramokz/phantom-camera @21d3762 (2026-10-07) | MIT | addon, plugin 0.11.0.3 | 0/68 | 2 2 2 2 0 | copy-adapt / use as addon |
| 5 | nezvers/Godot-GameTemplate @d5d8d15 (2026-06-18) | MIT | 4.7 | 0 errors/308 (52 stale-UID warnings) | 2 2 2 1 0 | copy-adapt |
| 6 | bitbrain/beehave @fe58915 (2026-09-20) | MIT | 4.7 | 2/349 (script template `_BASE_`, debugger message; benign) | 1 2 1 n/a 2 (gdUnit4, 29) | copy-adapt / addon |
| 7 | derkork/godot-statecharts @76d226a (2026-06-26) | MIT | feature "4.0" | 5/184 (C# example, vendored GUT) | 2 2 2 n/a 2 (GUT, 33) | addon / design |
| 8 | peter-kish/gloot @6b09b87 (2026-07-14) | MIT | 4.7 | 0/84 | 1 1 1 n/a 1 (6) | copy-adapt |
| 9 | filipbasara/trauma-gd @d4afab1 (2026-07-27) | MIT | 4.4+ (README) | 0/4 | 2 2 2 n/a 0 | copy-adapt (152 LOC) |
| 10 | symbol24/Simple-Scene-Manager @0b959e4 (2024-09-13) | MIT | 4.3 | 0/10 | 2 2 2 2 0 | design (123 LOC) |
| 11 | nathanhoad/godot_dialogue_manager @d583f01 (2026-10-14) | MIT | 4.7 (README 4.6+) | 4 errors + 4 warnings/103 (C# loaders absent: no dotnet) | 2 2 1 n/a 2 (21) | addon (dialogue, not a P-id) |
| 12 | dialogic-godot/dialogic @701b67b (2026-08-30) | MIT | 4.2 (CI project) | loaded as unregistered plugin: 8/348 (missing `Dialogic` autoload, editor-only calls); clean inside open-rpg | 2 1 2 n/a 1 (7) | addon (not a P-id) |
| 13 | Phazorknight/Cogito @676be6d (2026-10-10, **codeberg**) | MIT | 4.6 | 2/510 (theme references font files absent from the repo) | 1 2 2 2 0 | copy-adapt selected files |
| 14 | KenneyNL Starter-Kit-3D-Platformer @3fa8a04, -FPS @185fd23, -City-Builder @4535092, -Racing @2f2e5f2 (2026-03/08) | MIT code, CC0 assets (README) | 4.6 | 0 errors each (Racing: 1 stale-UID warning) | 0-1 2 1-2 1-2 0 | tiny-scale examples (<260 LOC); typed return ratio 0.00-0.15, so style is beginner-level |
| 15 | limbonaut/limboai @df8933d (2026-10-04) | MIT | 1.8.x for 4.6+ | **blocked**: needs the LimboAI GDExtension/module (`BTPlayer` unknown to the stock binary); 17 scenes fail | 2 2 2 2 0 (tests are C++) | design only until RP.H tests the GDExtension release |
| 16 | kidscancode/godot_recipes @bde6406 (2024-07-14) | MIT | docs | n/a (Hugo site) | untyped snippets | exclude as code source |
| 17 | NoelFB/Celeste @1b0ce45 (2021-08-05) | MIT (code; game assets excluded, README) | C# / XNA | n/a | n/a | design reference only (`Source/Player/Player.cs`, 5471 lines) |

### Complete games (architecture reference)
| Repo @commit | Licence | Godot | Size | Load-check [Run] | Autoloads | Notes |
|---|---|---|---|---|---|---|
| Yeldham/librerama @740d349 (codeberg) | GPL-3 | 4.6 | 87 scripts, 8.2k LOC | 0/183 | 2 (GameManager, ArcadeManager) | typed 1.00/0.97. Settings and save via `ConfigFile` (`user://settings.ini`, `user://save.ini`). Design only. |
| sourceofmana/sourceofmana @095803f | MIT code, art per-file credits | 4.7 | 236 scripts, 19.9k LOC | 0/455 (6 warn) | 3 | MMORPG; 21 dirs under `sources/` (`actor`, `ai`, `map`, `network`...). Ret-typed ratio 0.25. |
| max99x/wutw-public @57f41aa | CC0 1.0 | 4.7 | 857 scripts, 50.9k LOC, 65 Resource scripts | **not loadable**: Wwise addon, GodotSteam and a C++ GDExtension (`wutw-gdext`); a scripts-only copy gave 80 script errors, mostly those missing types | 12 | README calls it "complete, production-tested reference". Audio stripped. Use for data-driven content (P23), save (`GlobalSaveGame`), settings. Copy-adapt is legal (CC0). |
| sunder/sunder @d6f5f1b (codeberg) | AGPL-3 | 4.7 | 77 scripts, 2.2k LOC | **pending/see note** | 2 (Settings, Game) | GUT tests for `Health`, `Flag`, `Scoreboard`. Design only. |
| hurrycurry/hurrycurry @bae9a9e (`client/`) | AGPL-3 | 4.6 | 188 scripts, 7.3k LOC | 12/394 (scenes: `Parameter "material" is null`, cause unverified [U], maybe dummy renderer) | 8 | typed ret 0.25. Design only. |
| supertuxparty @4812d74 (gitlab) | GPL-3 (art/music separate) | 4.2 | 108 scripts | 99 errors, 35 scene fails (missing imported textures, stale UIDs) [U whether import-related] | 5 | older style (typed 0.69/0.39). Skip. |
| P1-X-in/Tanks-of-Freedom-3-D @dbe629e | MIT (code + gfx) | 4.4 | 292 scripts, 18.4k LOC | script-only copy only (assets 2.1 GB), inconclusive | 13 | typed 0.06 var / 0.07 ret: pre-typing style. Exclude as style reference. |
| Quaint-Studios/Reia @05348f8 | AGPL-3 | 4.7 | 163 scripts | **blocked**: Rust `RustCore` GDExtension and GECS missing | 10 | ECS-based; design only. |

## Pattern id -> candidate files (all paths exist in the clones; deepen in RP.A-K)
`R=` the refs dir. Use 'adapt' only for MIT/CC0 rows; GPL/AGPL rows are read-only.

| P-id | Best candidates (file paths under R) | Caveat |
|---|---|---|
| P01 platformer | `godot-demo-projects/2d/platformer/player/player.gd` (88 lines; API usage: `get_gravity()`, `move_toward`, `floor_stop_on_slope`); params only: `Ultimate-Platformer-Controller-2D/UltimatePlatformerController.gd` (names: timeToReachMaxSpeed, coyoteTime, jumpBuffering, descendingGravityFactor) | neither has coyote/buffer in the demo; Ultimate adds `velocity.y += appliedGravity` with no `delta` (lines ~462) [Src]; Expandable does not compile [Run]. Write own reference. A grep for `coyote` also hits `reia/_old_code/features/player/*` (AGPL ECS code, not read). |
| P02 slopes/platforms | `godot-demo-projects/2d/kinematic_character/` (`player/player.gd`, `world.tscn` one-way), `2d/physics_platformer/platform/one_way_platform.tscn`, `2d/platformer/level/platforms/platform.tscn` (AnimatableBody2D), `2d/physics_tests/tests/functional/test_character.gd` (snap / stop-on-slope option matrix) | `physics_tests` are interactive scenes, no assertions found in the file read |
| P03 3D controller | `godot-demo-projects/3d/platformer/player/player.gd` + `follow_camera.gd`, `Starter-Kit-3D-Platformer/scripts/player.gd`, `Starter-Kit-FPS/scripts/player.gd`, `phantom-camera/addons/phantom_camera/examples/scripts/3D/player_controller_first_person.gd` / `..._third_person.gd`; design: `sunder/scripts/entities/player.gd` | Kenney kits are weakly typed |
| P04 state machine | `godot-demo-projects/2d/finite_state_machine/state_machine/state_machine.gd`, `state.gd`; `godot-statecharts/addons/godot_state_charts/state_chart.gd` (+ `tests/`) | gd-YAFSM excluded (typed 0.10) |
| P05 dash/wall | `nezvers-template/addons/top_down/scripts/actor/DashAbility.gd` (typed, cooldown, after-image) | Expandable `SpecialMovements/Dash.gd`, `WallJump.gd` come from a non-compiling project: read only |
| P06 2D camera | `phantom-camera/addons/phantom_camera/scripts/phantom_camera/phantom_camera_2d.gd`, `trauma-gd/addons/trauma/camera_shake.gd`, `godot-open-rpg/src/field/field_camera.gd` (limits from gameboard bounds) | GDQuest `godot-make-pro-2d-games/actors/camera/ShakingCamera.gd` is Godot 3: exclude |
| P07 3D camera rig | `phantom-camera/.../examples/scripts/3D/player_controller_third_person.gd` (SpringArm3D); design: `sunder/scenes/entities/player/player.tscn`; `godot-demo-projects/3d/physics_interpolation/player.gd` | |
| P08 level structure | `godot-open-rpg/src/field/map.gd`, `src/field/gameboard/gameboard.gd`, `overworld/maps/`; `Maaack-template/scenes/game/levels/level.gd`, `level_1.gd` | |
| P09 components | `nezvers-template/addons/top_down/scripts/` (`actor/`, `damage/`, `pickups/`, `triggers/`) | no tests |
| P10 flow / scene manager | `Maaack-template/addons/maaacks_scene_loader/base/nodes/autoloads/scene_loader/scene_loader.gd` (threaded `ResourceLoader`), `scripts/level_and_state_manager.gd`; `godot-open-rpg/src/common/screen_transitions/screen_transition.gd`; `godot-demo-projects/loading/load_threaded/load_threaded.gd`, `loading/scene_changer/` | |
| P11 autoloads | counts in the games table; `godot-demo-projects/loading/autoload/` | anti-example: wutw (12), tof2 (13) |
| P12 pause & menus | `Maaack-template/addons/maaacks_game_template/base/nodes/utilities/pause_menu_controller.gd`, `scenes/windows/pause_menu.gd`; `godot-demo-projects/misc/pause/pause_button.gd`, `2d/platformer/gui/pause_menu.gd` | Maaack sets `process_mode = 3` in `scenes/game/game.tscn` |
| P13 save/load | `godot-demo-projects/loading/serialization/save_load_json.gd`, `save_load_config_file.gd`; `librerama/managers/arcade_manager.gd` (`save_data`, design); `wutw/wutw/utils/save_game.gd` (autoload `GlobalSaveGame`, CC0; not read in detail) | Maaack `GlobalState` saves `user://global_state.tres` [Src: `base/nodes/state/global_state.gd:4`]: do not copy |
| P14 settings/remap | `godot-demo-projects/gui/input_mapping/KeyPersistence.gd`, `Maaack-template/addons/maaacks_game_template/base/nodes/config/player_config.gd` (`ConfigFile`), `app_settings.gd` | |
| P15 input contexts | `Cogito/addons/cogito/Scripts/input_router.gd` (input stack, one consumer; PROCESS_MODE_ALWAYS), `Maaack-template/.../utilities/input_helper.gd` | |
| P16 enemy AI | `beehave/addons/beehave/nodes/beehave_tree.gd` (+ gdUnit4 tests), `Cogito/addons/cogito/CogitoNPC/npc_states/npc_state_chase.gd` + `detection/sight_detection.gd`, `godot-demo-projects/2d/platformer/enemy/enemy.gd` (enum FSM); limboai blocked | |
| P17 navigation | `godot-open-rpg/src/field/gameboard/pathfinder.gd` (AStar2D grid wrapper), `godot-demo-projects/2d/navigation`, `3d/navigation`, `2d/navigation_astar` | |
| P18 spawning/projectiles | `godot-demo-projects/2d/platformer/player/bullet.gd`, `gun.gd`, `2d/bullet_shower`; `nezvers-template/addons/top_down/scripts/weapon_system/` | |
| P19 hit/hurt/layers | `nezvers-template/addons/top_down/scripts/damage/` (`DamageSetup.gd`, `HealthResource.gd`, `DamageCooldown.gd`); tests for health: `sunder/tests/test_health.gd` (AGPL, read) | no layer-matrix reference found yet |
| P20 animation state | `godot-demo-projects/3d/platformer/player/player.gd` (AnimationTree), `2d/skeleton/player/player.gd`, `2d/role_playing_game/combat/combatants/combatant.gd` | |
| P21 HUD / responsive | `godot-demo-projects/gui/multiple_resolutions`, `gui/theming_override`; `Maaack-template/scenes/menus/` | no 21:9 reference found |
| P22 inventory | `gloot/addons/gloot/core/inventory.gd`, `inventory_item.gd`, `stack_manager.gd` (model) with `addons/gloot/ui/` (view) and `tests/`; `godot-open-rpg/src/common/inventory.gd`; `wyvernbox/` (MIT, 4.4) ; `godot-demo-projects/gui/drag_and_drop` | |
| P23 data-driven | `godot-open-rpg/src/combat/battlers/battler_stats.gd` (Resource), `nezvers-template/addons/top_down/` (51 Resource scripts), `wutw/wutw/` (65 Resource scripts, CC0) | |
| P24 audio | `Maaack-template/addons/maaacks_music_controller/base/scripts/music_controller.gd` (autoload, persists across scenes), `godot-open-rpg/src/common/music/music_player.gd`, `godot-demo-projects/audio/` | |
| C1 vertical slice | `Maaack-template` (menu, levels, pause, win/lose, options), `godot-open-rpg`, `librerama` (design) | |

## Exclusion list
- `GDQuest/godot-make-pro-2d-games` @7290681 (2019): Godot 3 project; 109 of 205 scripts/scenes error on 4.7, 2,833 idiom hits. Its licence is MIT but it teaches `KinematicBody2D`/`yield`.
- `benmarz/minimum_game` @c134361 (2020): Godot 3; 13 errors/34 files; 382 idiom hits.
- `Expandable-Platformer-Controller-2D` @b1128f3: **fails to compile on 4.7**: `Parse Error: Not all code paths return a value` at `PlayerController/PlatformerController2D.gd:109` and `:114` (`_property_can_revert`, `_property_get_revert`) [Run: `log_Expandable-Platformer-Controller-2D_load.txt`]. Also the Asset Library entry id 3494 points to commit 5a96ccc, not this HEAD.
- `Ultimate-Platformer-Controller-2D` @9ce6580: loads, but gravity is added without `delta` (`velocity.y += appliedGravity`) and coyote/buffer use `await get_tree().create_timer()` (frame-rate dependent, not tick-deterministic) [Src]. One 510-line file with every feature behind booleans. Keep as a trap exhibit for RP.A, not as a reference.
- `kidscancode/godot_recipes`: last commit 2024-07-14 (before 4.3); 12 of 117 pages under `src-4/content` still have Godot-3 idioms (`export var`, `yield`); snippets, 28 typed `var` lines across 349 gdscript blocks; no runnable project.
- `imjp94/gd-YAFSM` @a4241b1: typed 0.10, 44 idiom hits.
- `crystal-bit/godot-game-template` @e9dc892: aborts headless (exit 134) in its own `debug_menu.gd:430` autoload (`Invalid operands 'Object' and 'Object' in operator '%'`); 2020 design.
- `P1-X-in/Tanks-of-Freedom-3-D`, `supertuxparty`: pre-typing style or stale UIDs; keep only for scale facts.
- Anything under `godot-demo-projects/networking`, `mobile`, `xr`: not relevant to P01-P24.

## Traps for topic agents (verified in source)
- Maaack `GlobalState.save()` writes `user://global_state.tres` (a Resource): loading a user-editable `.tres` can instantiate scripts. Prefer JSON (`save_load_json.gd` in the official demos) per P13.
- Official `2d/platformer/player/player.gd` hard-codes `const WALK_SPEED/JUMP_VELOCITY` (not exposed) and has no coyote/buffer: copying it fails P01 targets.
- `open-rpg` README requires 4.7.2+, our binary is 4.7.0; it loaded without errors, but treat runtime behaviour as untested.
- Addon-style repos (dialogic, phantom-camera, trauma-gd) have no `project.godot` at the root; load-checks used a throwaway project with the addon copied, plugin not enabled, so autoload-dependent scripts report errors that are an artefact (dialogic).
- Stale UID warnings (`invalid UID ... using text path instead`) are common (nezvers 52, supertuxparty 99): harmless but they appear as WARNING in logger-based load-checks.

## Draft refs.yaml
```yaml
# commit = HEAD at clone time (2026-10-15). paths relative to repo root. use: adapt | design | exclude
- name: godot-demo-projects
  url: https://github.com/godotengine/godot-demo-projects
  commit: b761b4cd5718a7118f2c95eb55f181d0a5f004f1
  licence: MIT
  godot_version: "4.7"
  use: adapt
  patterns: [P01, P02, P03, P04, P10, P12, P13, P14, P17, P18, P20, P21, P22, P24]
  paths: [2d/platformer/player/player.gd, 2d/kinematic_character/player/player.gd, 2d/finite_state_machine/state_machine/state_machine.gd, 3d/platformer/player/player.gd, loading/load_threaded/load_threaded.gd, loading/serialization/save_load_json.gd, gui/input_mapping/KeyPersistence.gd, misc/pause/pause_button.gd, gui/multiple_resolutions, gui/drag_and_drop]
- name: Maaack-template
  url: https://github.com/Maaack/Godot-Game-Template
  commit: 6849d6c352dafe8ed54b5fa4f4b9774adfca31c8
  licence: MIT
  godot_version: "4.7"
  use: adapt
  patterns: [P10, P11, P12, P14, P15, P24, C1]
  paths: [addons/maaacks_scene_loader/base/nodes/autoloads/scene_loader/scene_loader.gd, scripts/level_and_state_manager.gd, addons/maaacks_game_template/base/nodes/utilities/pause_menu_controller.gd, addons/maaacks_game_template/base/nodes/config/player_config.gd, addons/maaacks_music_controller/base/scripts/music_controller.gd]
  note: global_state.gd saves a .tres to user:// - do not copy that part
- name: godot-open-rpg
  url: https://github.com/gdquest-demos/godot-open-rpg
  commit: d59f2f71bc046ac53239a4e590861269e7100a36
  licence: MIT (code); assets CC0 per CREDITS.md
  godot_version: "4.7 (README: 4.7.2+)"
  use: adapt
  patterns: [P06, P08, P10, P16, P17, P22, P23, P24, C1]
  paths: [src/field/field_camera.gd, src/field/gameboard/pathfinder.gd, src/field/map.gd, src/common/screen_transitions/screen_transition.gd, src/common/inventory.gd, src/combat/battlers/battler_stats.gd, src/common/music/music_player.gd]
- name: phantom-camera
  url: https://github.com/ramokz/phantom-camera
  commit: 21d3762492e2dc51b448f55438b89b3c19349f96
  licence: MIT
  godot_version: "addon 0.11.0.3 (min version not verified)"
  use: adapt
  patterns: [P06, P07]
  paths: [addons/phantom_camera/scripts/phantom_camera/phantom_camera_2d.gd, addons/phantom_camera/scripts/phantom_camera/phantom_camera_noise_emitter_2d.gd, addons/phantom_camera/examples/scripts/3D/player_controller_third_person.gd]
- name: nezvers-template
  url: https://github.com/nezvers/Godot-GameTemplate
  commit: d5d8d15887423b3a8acf0502efb6271c600a80bc
  licence: MIT
  godot_version: "4.7"
  use: adapt
  patterns: [P05, P09, P18, P19, P23]
  paths: [addons/top_down/scripts/actor/DashAbility.gd, addons/top_down/scripts/damage/DamageSetup.gd, addons/top_down/scripts/damage/HealthResource.gd, addons/top_down/scripts/weapon_system]
- name: beehave
  url: https://github.com/bitbrain/beehave
  commit: fe589153fa780a3f88989578ceb5f539afffb7c2
  licence: MIT
  godot_version: "4.7"
  use: adapt
  patterns: [P16]
  paths: [addons/beehave/nodes/beehave_tree.gd, test]
- name: godot-statecharts
  url: https://github.com/derkork/godot-statecharts
  commit: 76d226a3efac66a72aea825382b320c94808f409
  licence: MIT
  godot_version: "4.0+ (feature tag)"
  use: adapt
  patterns: [P04, P16]
  paths: [addons/godot_state_charts/state_chart.gd, tests]
- name: gloot
  url: https://github.com/peter-kish/gloot
  commit: 6b09b87ac07a8536779ef1ab0fafc7e99830f948
  licence: MIT
  godot_version: "4.7"
  use: adapt
  patterns: [P22]
  paths: [addons/gloot/core/inventory.gd, addons/gloot/core/inventory_item.gd, addons/gloot/core/stack_manager.gd, tests]
- name: trauma-gd
  url: https://github.com/filipbasara/trauma-gd
  commit: d4afab1ab92cececb730defa6b6cf85c1ef8d19f
  licence: MIT
  godot_version: "4.4+ (README)"
  use: adapt
  patterns: [P06]
  paths: [addons/trauma/camera_shake.gd]
- name: Cogito
  url: https://codeberg.org/Phazorknight/Cogito
  commit: 676be6dd6f412c87b391b51593bc4bb356571630
  licence: MIT
  godot_version: "4.6"
  use: adapt
  patterns: [P15, P16, P22, P03]
  paths: [addons/cogito/Scripts/input_router.gd, addons/cogito/CogitoNPC/npc_states/npc_state_chase.gd, addons/cogito/CogitoNPC/detection/sight_detection.gd]
- name: Simple-Scene-Manager
  url: https://github.com/symbol24/Simple-Scene-Manager
  commit: 0b959e40cd2259f11d20574e11eb16026f923045
  licence: MIT
  godot_version: "4.3"
  use: design
  patterns: [P10]
  paths: [addons/SimpleSceneManager/Code/scene_manager.gd]
- name: godot_dialogue_manager
  url: https://github.com/nathanhoad/godot_dialogue_manager
  commit: d583f0101c904ec352e9acfdf39efb45852ce8c6
  licence: MIT
  godot_version: "4.7 (README 4.6+)"
  use: adapt
  patterns: [C1]
  paths: [addons/dialogue_manager, tests]
- name: dialogic
  url: https://github.com/dialogic-godot/dialogic
  commit: 701b67bbe60114e010476d1685f7de1261091c29
  licence: MIT
  godot_version: "4.2 (CI project)"
  use: design
  patterns: [C1]
  paths: [addons/dialogic]
- name: Starter-Kit-3D-Platformer
  url: https://github.com/KenneyNL/Starter-Kit-3D-Platformer
  commit: 3fa8a04b1c01ab23db43123d4ce814a34c3fc7f0
  licence: MIT (code), CC0 (assets, README)
  godot_version: "4.6"
  use: design
  patterns: [P03]
  paths: [scripts/player.gd]
- name: Starter-Kit-FPS
  url: https://github.com/KenneyNL/Starter-Kit-FPS
  commit: 185fd2326d74a5cf858cffc616f87cf9696f9cc0
  licence: MIT (code), CC0 (assets, README)
  godot_version: "4.6"
  use: design
  patterns: [P03, P18]
  paths: [scripts/player.gd]
- name: librerama
  url: https://codeberg.org/Yeldham/librerama
  commit: 740d3492beb2b68b94a99ba46b463d08443ed360
  licence: GPL-3.0
  godot_version: "4.6"
  use: design
  patterns: [P10, P11, P13, P14, C1]
  paths: [managers/arcade_manager.gd, managers/game_manager/game_manager.gd, nanogame_player]
- name: sourceofmana
  url: https://github.com/sourceofmana/sourceofmana
  commit: 095803fe9bf496cafcfeebf6a62ae591593491bf
  licence: MIT (code); art per LICENSE.md credits
  godot_version: "4.7"
  use: adapt
  patterns: [P08, P11, P16, P23, C1]
  paths: [sources/ai/AICommons.gd, sources/system/FileSystem.gd, sources/actor, sources/map/Map.gd]
- name: wutw
  url: https://github.com/max99x/wutw-public
  commit: 57f41aa7a17213e54be841596baab4fa5f4b9774
  licence: CC0-1.0
  godot_version: "4.7"
  use: adapt
  patterns: [P11, P13, P14, P23, C1]
  paths: [wutw/main.gd, wutw/cards, wutw/settings, wutw/pause_menu]
  note: needs Wwise, GodotSteam and wutw-gdext (C++) to load; not loadable in this environment
- name: sunder
  url: https://codeberg.org/sunder/sunder
  commit: d6f5f1b3ec8170099257566068756b536b4661aa
  licence: AGPL-3.0
  godot_version: "4.7"
  use: design
  patterns: [P03, P07, P11, P19]
  paths: [scripts/entities/player.gd, tests/test_health.gd]
- name: hurrycurry
  url: https://codeberg.org/hurrycurry/hurrycurry
  commit: bae9a9e419b60e37a4efb52bfcac7df44e61412c
  licence: AGPL-3.0
  godot_version: "4.6"
  use: design
  patterns: [C1]
  paths: [client/game.gd, client/global.gd]
- name: limboai
  url: https://github.com/limbonaut/limboai
  commit: df8933d3e1a0e7884efb640c0e363140741c50cb
  licence: MIT
  godot_version: "1.8.x for 4.6+ (README table)"
  use: design
  patterns: [P04, P16]
  paths: [demo, tests]
  note: needs native extension; untested here
- name: Celeste
  url: https://github.com/NoelFB/Celeste
  commit: 1b0ce45c75e05649ae91b44a8bb6b196684e4352
  licence: MIT (code only)
  godot_version: "n/a (C#)"
  use: design
  patterns: [P01, P05]
  paths: [Source/Player/Player.cs]
```

## Clone paths for topic agents
All clones: `/tmp/claude-0/-home-user/77c17b82-ea72-5e78-90c8-1959b76a4dc3/scratchpad/dl/refs/<name>/`, where `<name>` is the `name` in the YAML, plus extras: `Expandable-Platformer-Controller-2D`, `Ultimate-Platformer-Controller-2D`, `wyvernbox`, `gd-YAFSM`, `godot-make-pro-2d-games`, `minimum_game`, `crystal-bit-template`, `tof2`, `supertuxparty`, `reia`, `godot_recipes`, `Starter-Kit-City-Builder`, `Starter-Kit-Racing`. Re-run a load-check: `scripts/rp_2_census/loadcheck3.sh <name> <subdir|.|NEWPROJ|ADDON:x> [label]` (edit the paths at the top).

## Blocked sources
- `KenneyNL/Starter-Kit-2D-Platformer`: no such repo (git asks for credentials).
- `github.com/Phazorknight/Cogito`: not found; real home is codeberg.
- github.com web, api.github.com: not used (blocked); the Asset Library API (`godotengine.org/asset-library/api/asset`) works with `curl` but returns 403 to Python `urllib` (user agent).
- Asset Library `godot_version` filter: `godotengine=4.7` returned 0 results; `godot_version=4.3` works (the API compares against assets' declared version, not 4.7).
- LimboAI GDExtension release binary, GodotSteam, Wwise: not fetched.

## Open questions
- Which controller does RP.A adopt for P01: write a new one (recommended) or repair `Ultimate-Platformer-Controller-2D` (add `delta`, replace `await` timers with physics-tick counters)?
- LimboAI via its GDExtension release: loadable with the stock 4.7 binary? RP.H to test (the release asset download is allowed).
- hurrycurry "material is null" scene errors and supertuxparty import errors: real defects or headless-renderer artefacts? [U]
- No reference found yet for: P19 collision layer matrix, P21 ultrawide layout test, P09 inheritance-depth check, P02 moving-platform carry.
- Whether `wutw` loads once Wwise/GodotSteam/gdext binaries are obtained (needs the Steam/Wwise SDK licences).
