# R1.6 The three talks behind "Your Game Is A Harness"

## Answer
- All three talks were located (YouTube embed IDs in the article) and full primary-source transcripts were obtained, so nothing below comes from memory. Tag convention: [Doc: <video or page URL> @h:mm:ss] = transcript text at that timestamp; [Run] = how it was fetched; [Unverified] = my inference.
- Common core, stated by all three: one plain-data world state, no engine types in it. A command or turn-order goes in, a stream of events or "receipts" comes out. Views (animation, audio, UI, achievements) only consume the events. Replay, undo, save/load, headless AI runs, and bug repro all fall out of that.
- Solium Infernum is the most concrete: a pure C# sim library, a whole-game-state JSON snapshot per turn, nested "game events" as receipts, a dumb Unity view, ~2,500-3,000 tests, and a headless multi-seed runner.
- Dreams (Alex Evans): the whole game is one `G` block, each frame is `new G = f(old G, input packet)`. That is bit-exact determinism, input-log replay, crash-to-PNG repro, and trivial undo. He says it was slow and culturally annoying, and probably not right for most games.
- Cronin (Monster Train): the "blackbox" part is a short proposal (about 2 min), not a shipped design. Monster Train itself did NOT have it and he lists the pain that caused. The captions never use the word "blackbox" and the talk is titled "Off The Rails".
- Godot takeaway: keep the sim in RefCounted/Resource GDScript with no Node dependencies, drive it with a command stream, emit events, and let nodes be disposable views. Details in the last section.

## Sources and status

| Talk | URL | Transcript status |
|---|---|---|
| Wookash Podcast, "Game Architectures with Alex Evans and Anton Mikhailov" (2h53m) | https://www.youtube.com/watch?v=mFBmoCv5EcQ | OBTAINED: YouTube English auto-captions via yt-dlp. Speakers are unlabelled, so attribution to Alex vs Anton is by context only. Auto-caption errors are likely (e.g. "Dave serialization"). |
| Brian Cronin, "Off The Rails: Lessons from Monster Train Development" (Roguelike Celebration, ~31 min incl. Q&A) | https://www.youtube.com/watch?v=qO3CIpP62Q0 | OBTAINED: YouTube English auto-captions. |
| Game Data Podcast Ep 4 (page says "third episode"), "William Dyce and Peter McIntosh on Solium Infernum" (1h37m, 2025-01-17) | https://www.gamedatapodcast.com/p/solium-infernum-william-dyce-peter-mcintosh-league-of-geeks ; video https://www.youtube.com/watch?v=lij4Mlc8I4I | OBTAINED: Substack's own timestamped transcript JSON (`transcription.json`, linked from the post API). Not auto-captions, so higher quality. Speakers: Dyce and McIntosh are not separated in my text, so I attribute to "the Solium devs"; McIntosh is tech lead and Dyce is senior technical designer [Doc: gamedatapodcast page]. |

How the links were found: the article HTML only contains three `youtube-nocookie.com/embed/<id>` iframes (`lij4Mlc8I4I`, `mFBmoCv5EcQ`, `qO3CIpP62Q0`), in the order Dreams, Cronin, Solium by the surrounding text. Titles were confirmed via `youtube.com/oembed` [Run: curl oembed -> JSON titles above, HTTP 200]. The Wookash episode was not otherwise identified; the article says "some of the episodes ... Dreams", and the embedded one is this episode. Kukshtel's text calls the Cronin talk "blackbox game architecture" but that is his label [Doc: article].

[Run] details:
- `yt-dlp` default failed: "Sign in to confirm you're not a bot" (HTTP 429 on the watch page).
- `yt-dlp --skip-download --write-auto-subs --sub-langs en --extractor-args "youtube:player_client=tv,web_safari,android_vr"` succeeded and wrote `.en.vtt` for both videos. Recipe worth keeping for the harness.
- Solium: the Substack post API `https://www.gamedatapodcast.com/api/v1/posts/<slug>` returns `podcastUpload.transcription.cdn_url`, a signed substackcdn.com URL for the transcript JSON (2.1 MB, HTTP 200).
- Raw files are under `scratchpad/dl/talks/` (untrusted data, not summarised beyond what I read).

---

## Talk 1: Solium Infernum (Game Data Podcast), strongest source

Source status: full transcript read. Timestamps are from the Substack transcript.

Key implementation points:
1. **Sim is a separate engine-agnostic C# library.** Driver: they did not want the server to be "Unity deploys", so the sim core and everything for multiplayer is "completely agnostic from Unity", "just raw C#", run in PlayFab/Azure Functions. [Doc: gamedatapodcast ep @0:06:09-0:06:40]
2. **Same core, local or remote.** A thin `IService` picks local or remote session; a local game sends the identical turn-order data to a local processing service on a thread. [Doc: ep @0:08:28-0:09:34]
3. **State = one big JSON snapshot.** The whole scenario/save is "one giant ... JSON file" of every game piece, player state and stats; compressed for transfer. Pain: serialising too much hit RPC size limits. [Doc: ep @0:15:51-0:16:46]
4. **A snapshot per turn, deterministic replay.** The server records a save state per turn; given the same sim version it is deterministic end to end, and replay is "just playing the saves". They never built multi-version sim support. [Doc: ep @0:17:44-0:18:21]
5. **Turn processing = deep-copy state, run queued actions, clear the list.** The turn "ready for processing" holds all planned moves, is deep-copied to make the next turn, actions run, then the list is cleared. Plans are part of the save state, so you can infer which action caused a change. [Doc: ep @0:19:51-0:20:25]
6. **Scrubber for debugging and AI.** Run the AI N turns, then scrub back and forward, "go back to the same seed, rerun". [Doc: ep @0:20:33-0:21:11]
7. **Headless batch runs.** Because the sim isn't Unity "you can just put it on a thread"; they ran multiple predetermined seeds for 50+ turns in parallel with progress bars. [Doc: ep @0:21:50-0:22:56]
8. **Tests first, 2,500-3,000 of them, ~75-80% automated.** Test-driven from project start (written in the Unity test runner, before art existed). Data-driven exhaustive tests: all 20 duel cards against each other (~400 tests); every ability's data describes its target-selection steps, and a harness "picks the first valid one" so any new ritual is auto-tested. [Doc: ep @0:23:29-0:25:39]
9. **AI behaviour encoded as tests.** E.g. "all AIs buy a legion by turn 10", "raise a power to level 4"; this surfaced non-AI regressions months later. [Doc: ep @0:25:45-0:27:12]
10. **View is a dumb choreography layer driven by "game events".** Sim returns nested receipts of what each action did (action -> effect -> damage -> death); a "turn outcome sequencer" in Unity plays them. The turn log UI reads the same events. Unity "doesn't know anything about the simulation core". [Doc: ep @0:28:58-0:31:17]
11. **Snapshot rendering plus snap-to-end-state.** First thing built: load a save and render the world flat in idle state. Each animation block snaps units to its expected start, runs, then places them at the expected end, so a missing/incorrect event can't leave the view wrong and "skip" is trivial. [Doc: ep @0:28:17-0:28:50, @0:30:05-0:30:49]
12. **Functional style with fat context objects.** Functions take game state, turn state, player, piece, destination, etc.; each atomic change returns a game event which is chained into the caller's event. The server protocol is only "I am player X, game Y, move piece Z via path". Data classes are thin. [Doc: ep @0:35:12-0:36:20, @0:37:48-0:38:15]
13. **Deliberately not ECS** (team burned by Unity's prototype ECS), but they drifted back: `GameItem` base class (players, abilities, rituals, schemes all derive), `GameEntity` later. Prefer driving behaviour by enums over type checks, "so we could really go fat". [Doc: ep @0:36:36-0:37:15, @1:09:32-1:09:54, @1:19:44-1:20:12]
14. **Problems and results.** An action can return a "problem" (pure serialisable data, ~140 subclasses) used both to refuse the action and to show UI previews and localised messages. Regret: not unifying problems and game events. [Doc: ep @1:13:37-1:16:15, @1:16:21-1:17:30]
15. **Serialization fuzz test.** Reflection finds every serialisable type, fills it with junk, round-trips, compares. [Doc: ep @1:14:39-1:15:36]
16. **Static data baked into saves.** Entities copy base stats at instantiation, so balance patches don't invalidate in-flight 4-month games or tutorial/puzzle saves; a dev console flags drifted saves. [Doc: ep @0:12:00-0:14:48]
17. **Information hiding for AI.** Two contexts: read-only vs mutable; a "knowledge processor" strips unseen info for the AI view. The AI still sometimes used the true state. Not a clean DMZ. [Doc: ep @0:40:24-0:43:00]
18. **Data authoring.** Spreadsheet-to-Unity sync built (months), then scrapped when a designer preferred Unity: "one source of truth that was versioned". Data lived as MonoBehaviour "data configs" wrapping sim-library C# structs, so no Odin; custom inspectors and an asset-query tool were needed. Sheets were still used for analysis. [Doc: ep @0:54:57-0:58:06, @1:00:00-1:01:44]
19. **Events as signals for schemes/achievements; modifiers recalculated, not attach/detach.** Objectives are event readers run at end of turn; stat modifiers are recomputed from scratch when dirty, which removes "attach but never detach" bugs. [Doc: ep @1:23:25-1:25:00, @1:28:00-1:31:20]

## Talk 2: Brian Cronin, Monster Train (Roguelike Celebration)

Source status: full auto-caption transcript read. The blackbox idea is only ~2 minutes (22:00-24:00) and presented as what he does in other projects ("a little over a year"), not as Monster Train's architecture.

Key points:
1. Monster Train began as a real-time prototype and "the prototype will become the product"; the turn-based game kept its code. [Doc: https://www.youtube.com/watch?v=qO3CIpP62Q0 @0:04:00-0:05:30]
2. Coroutine-driven logic bundled UI, input, SFX and rules together ("no separation of concern"). [Doc: same @0:05:30-0:06:30]
3. Damage previews (the red X) were essential, and needed a deterministic simulation. They did not plan for it, so the game loop ran as a coroutine with many "if preview mode, skip sound/warning" exceptions. [Doc: same @0:07:00-0:08:30]
4. Cards are "their own programming language": a card = data pointing at a C# effect script plus invisible "traits" that patch damage computation in code; behaviour is implicit in code, so designers couldn't control it and engineers wrote custom traits for specific cards. [Doc: same @0:12:00-0:13:30]
5. Proposed improvement: a domain-specific action graph (control-flow nodes, data-input nodes such as "energy spent", "discard pile size"), so designers rewire effects while engineers write small nodes. Not shipped in Monster Train. [Doc: same @0:13:30-0:15:30]
6. The in-game F8 feedback tool posts text, log file, save file and screenshot to Slack; the save restores to the start of the battle, since battles were deterministic only from there. [Doc: same @0:15:30-0:17:30]
7. Mixed gameplay logic and presentation leads to spaghetti with manager-to-object callbacks. [Doc: same @0:18:30-0:20:30]
8. **The proposed shape:** `WorldState` (data plus simple queries) <- `WorldEngine` (the only mutator) fed by `WorldCommand`s (move unit, play card, damage); the engine emits `WorldStateChange`s (unit moved, card played, unit died). Commands and changes are NOT one-to-one: a damage command may or may not yield a death, or may yield dozens of changes. [Doc: same @0:21:30-0:22:30]
9. Views subscribe to the changes they care about: SFX, achievements, animation. Input only generates commands. He maps it to MVC: state=model, engine=controller, changes=view. [Doc: same @0:22:30-0:23:30]
10. Benefits claimed: easier serialisation (save file, JSON), easier networking, and in Unity the GameObjects are "just a view" so the world might need no Unity code at all. [Doc: same @0:23:30-0:24:00]
11. In Q&A: with a world state, Monster Train could have verified runs server-side and saved mid-battle; one world state per run is fine, and snapshots of states allow rollback/networking. [Doc: same @0:27:00-0:28:30, @0:29:30-0:30:00]
12. Debugging callbacks relied on extensive categorised logging; he now advocates "not doing callbacks at all". [Doc: same @0:25:30-0:26:30]

Caveat: no timestamps here discuss replay, command streams as logs, or data tooling beyond the cards/graph discussion. Replay is implied only by "snapshots" and the save-file repro.

## Talk 3: Wookash Podcast with Alex Evans and Anton Mikhailov (Dreams)

Source status: full 2h53m auto-caption transcript. I read the architecture-relevant parts closely (0:26-0:35, 1:12-1:33, 1:44-1:56); the rest (tools, languages, hardware) was only keyword-scanned. Speaker attribution is by context: Alex Evans leads the Dreams architecture description [Unverified for individual lines].

Key points:
1. **Whole game = one pointer `G`.** Per frame you read `const G*` (last frame) and write a fresh `G` (next frame), "purely functional"; the only inputs are old `G` and the controller USB packet. [Doc: https://www.youtube.com/watch?v=mFBmoCv5EcQ @0:27:00-0:27:30]
2. **Read-only previous state gives cheap multithreading.** Renderer gets a round-robin of recent `G`s to interpolate; audio just grabs a const `G`. [Doc: same @0:27:30-0:28:00]
3. **Determinism checked on the fly.** Every frame, two groups of threads run the game and results are compared; any bit mismatch asserts immediately. [Doc: same @0:28:00-0:28:30]
4. **Undo/redo and save/load built first**, because Dreams is a UGC editor; everything is serialisable. [Doc: same @0:28:30]
5. **Crash repro by PNG.** On crash, save screenshot plus core dump; append the serialised last-good `G` after the end of the PNG; auto-upload. The dev loads it and the next frame crashes identically. They also store the boot snapshot and every input packet (~8 bytes each) so you can replay from the start. [Doc: same @0:28:30-0:30:00, @0:31:30-0:32:00]
6. **Limits:** replay is roughly real-time speed; network input was not recorded, so server-related bugs didn't reproduce. Works because the single-player core is "hermetically sealed" with a known input set. [Doc: same @0:32:00-0:33:00]
7. **Deletion = not copying yourself forward.** No defrag, ordering becomes cache-friendly naturally; storage is classic things/parts struct-of-arrays. [Doc: same @0:33:30-0:34:30]
8. **Downsides are said plainly.** "Uniformly slow" (rebuild every object every frame) but predictable at worst case; cultural cost of writing everything "like a shader"; parallelisation problems; Evans: "I don't think it's likely that it's a good architecture for many things". LBP before it was a conventional ECS. [Doc: same @1:22:00-1:24:30, @1:13:30-1:14:00]
9. **Brute force beats dirty flags.** Mikhailov's napkin math: 100,000 things is ~20-30 MB and ~1 ms to touch; then brute-force "instead of doing dirty flags". [Doc: same @1:24:30-1:26:30]
10. **Serialization approach.** Per-field annotation with macro introspection (the Media Molecule serializer) works for large projects but is annoying for toy apps; Evans' conclusion for hobby work is that the missing piece is organisation (state in one place), then serialising to JSON is easy. [Doc: same @1:33:00-1:37:30]
11. **Simplest possible state scales.** Ragdoll Kung Fu: one struct type for everything, indices not pointers, globals placed in a linker section and zipped, so mid-game join is "zip the bytes between two markers". Redis `fork()` snapshot gives the same idea at server scale. [Doc: same @1:44:30-1:49:30]
12. **Undo by copying everything.** "The dumb undo" (copy-on-write whole-state copy) beats a command-pattern undo/redo if state is copy-on-write. [Doc: same @1:51:00-1:52:30]
13. **Build the editor and iteration loop first.** "Iteration count is the only number that matters." [Doc: same @1:53:00-1:55:30]
14. **Content-addressed assets and dependency lists up front** (LBP/Dreams) to minimise round trips. Relevant to data tooling and caching, less to the sim. [Doc: same @1:14:00-1:21:30]

---

## Implications for Godot (inferences, tagged [Unverified] where they go beyond the talks)

1. **Sim as non-Node code.** Put rules in `RefCounted`/`Resource` classes (GDScript or C#) with no `Node`/`SceneTree` calls. Then `godot --headless --script` or a test runner can run thousands of turns without a window, as Solium ran on threads. Nodes are views. [Unverified: mapping; Solium/Cronin design]
2. **One root state object, serialisable as JSON or a Resource.** Solium uses one JSON snapshot; Dreams one `G`. In Godot a single root `Resource` with `@export` fields (or a Dictionary) gives `ResourceSaver`/`JSON.stringify` snapshots without writing a custom serializer. [Unverified]
3. **Command in, event stream out.** `apply(state, command) -> Array[Event]`, with events nested or causally linked (Solium) and not one-to-one with commands (Cronin). Views connect to events instead of to sim internals. Nodes should hold only view data such as the entity id, never the authoritative stats.
4. **Node lifetimes follow events, not the reverse.** Spawn/free view nodes by `EntityCreated`/`EntityRemoved` events keyed by a stable int id (Dreams and Ragdoll Kung Fu both use indices, not pointers; Solium uses game piece IDs). Never store `Node` references or `NodePath`s in sim state. Reload from a snapshot = clear the view container and rebuild from state (Solium "snapshot rendering").
5. **Turn-based: step per command; real-time: fixed tick.** Solium (turn-based) is trivially headless and replayable. For real-time, the Dreams model maps to a fixed-step `tick(state, input_packet)` called from `_physics_process` (or from a test loop) with the RNG seed in the state. Floats and Godot physics are not deterministic across platforms and engines [Unverified: not from talks], so treat the sim as logic-only or use fixed-point/integers when replay matters. Monster Train's real-time-to-turn-based experience is the warning that retrofitting determinism costs a lot.
6. **Replay = seed + initial snapshot + command log.** Dreams records start snapshot plus inputs; Solium records per-turn snapshots. The harness should write both a command log and periodic snapshots; add a "scrubber" (load snapshot N, re-run commands). Make this part of every bug report, like F8 feedback and the Dreams crash PNG.
7. **Harness hook: run N seeded games headless and assert invariants.** Solium's AI bars ("3 armies by turn 10") and exhaustive data-driven tests (every card vs every card, every ability auto-targeted) are directly agent-friendly. Add a Godot-side test that round-trips every state type through serialisation (their reflection fuzz test).
8. **Previews and AI reuse the same sim.** Monster Train's damage preview and Solium's AI planning both need cheap "apply on a copy" semantics. Design `apply` to work on a duplicated state (`duplicate(true)` is cost-relevant [Unverified]) from day one so previews do not need `if preview` branches.
9. **Data tooling.** Both Solium and Cronin say the same: designers need data they can edit with validation (Solium: Unity inspectors, custom ID pickers, asset query tool, spreadsheets for analysis only). Godot analogue: typed `Resource` files plus a validation script and JSON/CSV export for analysis; keep one versioned source of truth. Bake base stats into entity instances if saves must survive balance patches.
10. **Don't over-fix architecture.** Dreams devs say their architecture had real costs and is unlikely right for most games; Solium abandoned ECS purity and used inheritance plus enums. Recommend the sim/view split and command/event contract as the template, and leave ECS vs OO to the project.

## Blocked sources
- `youtube.com/watch` via yt-dlp default client: bot-check / HTTP 429 (worked around with `player_client=tv,web_safari,android_vr`).
- `youtubetotranscript.com/transcript?v=qO3CIpP62Q0`: HTTP 403.
- `wookash.com`: TLS self-signed certificate error (not pursued).
- `kylekukshtel.com` article itself was not refetched (I used the local raw copy only).
- Web search found no transcript or write-up for the Cronin talk or the Wookash episode. Not needed after yt-dlp succeeded.

## Open questions
- Does Kukshtel mean this Wookash episode specifically? The article says "some of the episodes ... Dreams", and Wookash has other Dreams-related guests; only the embedded episode was reviewed. Other episodes may add more.
- Dreams speaker attribution (Alex vs Anton) is unverified because auto-captions lack speaker labels. Check by listening to the cited timestamps before quoting by name.
- Auto-caption details like "Dave serialization system" and proper nouns could be wrong; verify key terms against the video if quoting.
- Dreams-style "pure function of previous G" has no Godot equivalent for engine-owned state (physics server, AnimationPlayer, particles). How much game logic can be moved out of those is project-specific and not answered by these talks.
