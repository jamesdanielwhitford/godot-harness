# "Your Game Is A Harness" by Kyle Kukshtel: structured write-up

Source: https://kylekukshtel.com/ai-harness-engineering-game-development-claude-code
Published October 10, 2026. It is a blog version of a 45-minute talk given at Indie Rodeo, Calgary, on 9/12/26. The author says the post is entirely human-written from his slides and is not a transcript.

**How I read it:** I read the full text and looked at all ~48 slide images, because much of the argument is in the slides: the "flywheel" diagram, the fat-struct and Command definitions, a Godot screenshot snippet, and the final harness diagram. The three embedded YouTube videos were not watched (Wookash podcast with the Dreams devs, Brian Cronin's Monster Train "Blackbox" talk, and the Solium Infernum Game Data Podcast episode). The linked dbreunig "How long contexts fail" post is used only through the excerpt shown on the slide. Anything marked **[Inference]** is my reading, not the author's claim.

---

## 1. Thesis and how the argument runs

**Thesis:** LLMs are not bad at games by nature. They fail because most of a game is **opaque to them**: it is not code or text they can read and act on. That makes it a **context problem**. The fix is to design the game itself so an agent can read it and drive it: deterministic, serializable, controllable by commands, runnable without the engine, and measurable as text. Do that and **the game becomes the harness**. In the author's words, "any game can easily be its own harness."

**How the argument flows:**
1. **Background.** The author built mood.site with ChatGPT and found that for web stacks there is "very little, if anything" an LLM can't do. Games kept failing.
2. **"LLMs are bad at games."** He gives two reasons: (a) far less public game source code to train on than web code, and (b) games contain a great deal that isn't code. Three.js one-shot demos only work because they make everything code (boxy primitives), and the results are "slop" with no authorial voice.
3. **The diagram.** For most software, CODE leads to a WORKING THING. For games, CODE plus "a million other annoying things like assets, platform delivery, etc." leads to a "DEFINITELY NOT REALLY WORKING THING."
4. **LLM basics.** A prompt has system, assistant and user parts. The whole history is re-sent on every turn, so context builds up. Bad content ("poison") compounds. Context engineering is about getting good information in with minimal pollution. From the slide: the non-code parts of a game have "no easy access by LLMs," so the model has to guess them, "which will likely be wrong," and that causes context rot.
5. **Reframe.** This is a context problem, not something built into games or LLMs. But "every game is a special disgusting flower": there is no standard tooling.
6. **Harnesses.** He defines the term and surveys existing harnesses (the GitHub list RyanAlberts/best-of-Agent-Harnesses). None of them "actually talk to your game," because the game is a black box. The goal is to "crack open the black box" by turning the non-code parts into code. His slide labels this "CODE (but now with more Code)," which leads to a working thing "(or much closer)."
7. **Concrete techniques**, in order around a "flywheel" loop: Fixed Random Seed, Deterministic State, Addressable State, Verifiable State, Impact Assessment, with an outer Screenshots and Progress loop.
8. **Wrap-up.** Put the tools on the flywheel and the whole agent turn takes "seconds." The loop is the game, so "Your game is a harness."
9. **Postscript caveat.** He is shipping a small project that uses *none* of this. The approach targets larger projects.

---

## 2. What "harness" means in the article

- **The author's definition:** "some set patterns of actions an agent is meant to take in response to some well (or loosely) defined expected input." Claude Code is named as a harness you probably already use, and harnesses "can be augmented, extended, distilled, abstracted, etc." for specific work.
- **What existing harnesses do:** they help answer "how can I better understand what I'm building, and guide that process." They tie in browser iteration, telemetry, profiling, and full SDLC work such as tickets and docs.
- **The gap:** none of them talk to *the game*. A general-purpose harness doesn't fix "games aren't just code."
- **His reframe:** the useful harness for games is **the game's own architecture plus a small set of CLI tools**, arranged as a fast, autonomous feedback loop. The final diagram is labelled "This is your game":

| Flywheel stage (slide label) | What it means | Concrete mechanism or tool named |
|---|---|---|
| Fixed Random Seed | One seeded RNG for all non-determinism | Single RNG source |
| Deterministic State | Exact save/load and reproduction of any state | "Fat Struct" / single `Thing` type; Blackbox Architecture |
| Addressable State | Change state through typed, serializable, text-authorable messages | Command Pattern |
| Verifiable State | Check changes without the engine | Tests on a standalone simulation (pure C# test project) |
| Impact Assessment | Did the change affect the real game as intended (performance, balance) | samply (text-dumpable CPU profiler); fixed gameplay scenarios |
| Screenshots → Progress (outer loop) | Visual check against a target, as a number | Engine screenshot API + layer toggles + odiff |
| Cross-cutting | "Can eliminate compile for sets of problems"; "VERY FAST, seconds per 'turn'" | External data (Depot, Sheets), runtime command playback |

- **Feedback loops:**
  - The **outer loop** is screenshot → diff against target → progress score.
  - The **inner loop** is the flywheel, where "an agent will spend most of its time, doing multiple turns on its own before going back to the screenshot comp/diff."
  - The goal is minimal changes, each verified quickly, on top of a "stable, 'boring' baseline."
  - Because the loop is fast it "can be run against every change, and not saved for only when it 'matters'."
- **Scaffolding:** mostly architectural (single object type, commands, simulation in its own DLL, external data) plus agent-readable tools (odiff, samply, your own data editor that the agent is "taught to use"). The article does **not** cover Claude Code mechanics such as CLAUDE.md, skills, hooks, MCP servers or subagents.

---

## 3. Why games are harder for LLMs than web/CRUD apps (per the article)

Stated in the article:
1. **Much of the game isn't code, so it is opaque.** "Games have a lot of stuff in them that isn't code." These parts are "effectively opaque to an LLM." If the game depends on "puppeting and transforming of that opaque stuff," the LLM "is going to fall over." The slide examples are "assets, platform delivery, etc."
2. **Opacity forces the model to guess, which pollutes context.** Slide: "No easy access to this by LLMs means that it has to be intuited by model, which will likely be wrong," which leads to context rot or failure. Wrong guesses stay in the history and compound ("Compounding Failure").
3. **Less training data.** There is "orders of magnitude less" public game source than high-quality web source. He admits this may partly be his own bias: as a 15-year game programmer he can spot bad game code, but he is less able to judge Svelte code.
4. **Many systems at once.** Games include all the layout work web apps do, "but only as a subset of the 100 other systems a game needs."
5. **No standard template or tooling.** "There is effectively 0 standardized tooling for anything," because every game has different needs ("every game is a special disgusting flower"). Web stacks have shared conventions; games don't.
6. **Visual checking is hard for models.** Before/after screenshots don't work well even for vision-capable models. They struggle to say what changed or whether it moved them closer to the goal. The whole image is "context pollution," because the model processes everything, not just the region you care about. He calls naive screenshots "its own form of context rot."
7. **Reproducing state is hard.** Iterating needs the agent to reach the same state repeatedly "without needing to churn through state replication failures." Typical games mix simulation with visuals and UI, so testing or reproducing a bug needs "the whole game running": models, sounds and scenes loaded. Failures then can't be pinned to one cause: "is it the simulation? The models? The scene design?"
8. **Compile and editor loops are slow.** Data written as code, or tweaks that need console bindings, put "testing basic value changes behind a compilation," which slows the agent. He also says outside contributors "don't even necessarily need editor access" once data is external, implying the editor is otherwise a bottleneck.
9. **Deep OOP class hierarchies.** "100 classes of 100 different types of objects" fill the context and create doubt about whether to extend, morph or add a class. They also make serialization hard: polymorphic deserialization, "There Be Dragons."
10. **Profilers are built for humans.** The Unity/Unreal profilers and dotMemory are GUI tools that are not "legible to the agent." He notes Unity is working on making its profiler readable by agents. "What AI really likes it to work with text (and lots of it)."

Topics the article does not address (flagged so they aren't attributed to it):
- **[Inference / not in article]** Game *feel*, timing and frame-dependent behaviour (input latency, animation curves, physics tuning, "juice") are never discussed. The verification ideas cover visuals (diffs), logic (tests on the simulation) and performance (profiling) only. Feel is not covered.
- **[Inference / not in article]** Physics or engine-level non-determinism (floating point, variable frame delta, multithreaded physics) is not discussed. The determinism advice is limited to RNG seeding and serializable state.
- **[Inference / not in article]** Scene and asset file formats (e.g. Unity YAML, Godot `.tscn`/`.tres`) are not discussed directly. "Assets" appears only as a broad category of non-code material. His approach goes around these formats by moving the source of truth into plain code and data, rather than teaching the LLM to edit them.
- **[Inference / not in article]** Audio and animation verification are not covered.

---

## 4. Key points, ranked

1. **It's a context problem: make the game legible.** LLM failures at games come from opaque, non-text game state. Turn as much of the game as possible into code, data or text the agent can read and change.
2. **Determinism and exact save/load from day one.** "How easily can you save and load an exact state in your game?" is the test. Adding it late is "VERY hard" and needs "fundamental changes … in the 11th hour."
3. **Separate the simulation from the engine (Blackbox Architecture).** The simulation lives in its own DLL as the source of truth. The engine is a "dumb" view that sends commands and receives state. This makes engine-free tests possible ("AI likes this!", "VERY FAST!!!!"), helps networking, and lets an LLM drive the game.
4. **Command Pattern as the agent's control interface.** Typed, serializable commands let you replay bugs, and an AI can write command sequences in text and run them against a live game with "no compiling required."
5. **Cut compile and iteration bottlenecks.** Keep data outside the code, deserialize it at runtime, and use no-compile changes. "Remove cycle iteration bottlenecks." The goal is "seconds per 'turn'."
6. **Single fat-struct object model ("A Tree Is A Dog").** One `Thing` type with an enum `Type` gives one source of truth, removes doubt about where changes go, and makes serialization one-path.
7. **Measure visual progress as a number (odiff), not by eye.** Compare a diff against the target rather than whole images. Crop. Toggle layers. Use the similarity percentage as a stable signal from turn to turn.
8. **Text-based profiling for impact assessment (samply).** Agents can then run the capture-and-iterate loop on their own.
9. **Good practice even without AI.** "A lot of these tips are good for game development in general."
10. **Scale caveat.** This pays off on larger projects. He used none of it on a small game he is shipping.

---

## 5. Checklist of practical recommendations

**Architecture (do early, ideally "before you write your first line of code")**
- [ ] Create **one seeded random source** at game start and route *every* non-deterministic call through it.
- [ ] Make **exact save/load** a core capability from the start, not a late feature.
- [ ] Use a **single object type** (`Thing` / "fat struct"): `enum Type`, `bool isAlive`, stat fields such as `attackDamage`, `walkSpeed`, `boatSpeed`. Branch on the enum. Even singletons fit, e.g. a `GameManager` type and a "Turn Number" field. (He says it isn't as memory-expensive as you might think and links Casey Muratori's computerenhance Q&A.)
- [ ] Treat the game as "a giant list of Things." Save and load through **one serialization path**. Avoid polymorphic deserialization.
- [ ] Use the **Command Pattern**. Instead of `myObject.hp += 1`, use a serializable command `{ enum Type (inc, dec, etc.); int value; string target }`. The slide notes `target` "is a big topic." Process all commands through one processor.
- [ ] **Record command streams** from a starting state so you can **replay bugs** without asking players for steps.
- [ ] Let commands be **authored as text** by you or the AI and **played back on a running game instance** without compiling.
- [ ] **Separate simulation from engine (Blackbox Architecture).** Put the simulation in its own library/DLL ("Plain C#"). The engine sends commands and gets updated state or diffs back, then acts on them without question. The simulation validates commands, e.g. movement targets; the engine may pre-filter.
- [ ] Use the same command interface for **any source**: Engine/View, Network, LLM, and so on.
- [ ] Build a **pure-code test project** that sends commands to the simulation and checks the resulting states, with standard tooling and no engine.

**Data**
- [ ] Move static "operational data" (type definitions, base stats) **out of code into an external data source**, deserialize it at runtime, and apply it during object creation, so that "Changing Field Values … can propagate at runtime."
- [ ] Make data changes testable **against a build**, without the editor or a recompile.
- [ ] Use a data editor: the author's **Depot** (depot-editor.com), **Google Sheets**, or a custom tool (Riot's game data server is linked). **Teach the agent to use your tools.**

**Visual verification**
- [ ] Use the engine's **screenshot API**. Slides show Unity `ScreenCapture.CaptureScreenshot`, a **Godot GDScript example** (`_unhandled_input` on a `'screenshot'` action calling `take_screenshot()`, which uses `get_viewport()…`), and a console `Shot` command.
- [ ] Add **toggles for UI and gameplay layers** so screenshots show only the layer under work. Slide: "Buffer shot prior to taking to filter out what you want/don't want."
- [ ] Don't give the model raw before/after pairs or whole-image comparisons. **Diff them** and compare the diff with the target ("Notes only comp," "Pure Signal").
- [ ] Use **odiff** (github.com/dmtrKovalenko/odiff) for a diff image and a **similarity percentage**. Crop to the region of interest. Use the score as the turn-by-turn progress metric.

**Impact assessment**
- [ ] Prefer **profilers that output text**. He recommends **samply** (github.com/mstange/samply): `samply record ./my-application my-arguments`. On Linux it may need `perf_event_paranoid` set to -1. On Windows, `samply record -a` with symbol servers. The agent can read samply's source and docs and run the loop alone.
- [ ] Add **game-specific checks** such as tests and **fixed gameplay scenarios** for balance impact. He mentions these but leaves the details to each game.

**Agent workflow and context hygiene**
- [ ] Keep each change to the **minimum needed** and **verify it quickly**. Keep a stable, "boring" baseline.
- [ ] Watch for **context pollution**. Keep only good information in context, because earlier errors compound.
- [ ] Make the full loop fast enough to run **on every change**.

**References he points to:** dbreunig's "How long contexts fail" (poisoning, distraction, confusion, clash); RyanAlberts/best-of-Agent-Harnesses; gameprogrammingpatterns.com Command chapter; Wookash podcast with Dreams creators; Brian Cronin's Roguelike Celebration talk on Monster Train's Blackbox architecture; Game Data Podcast episode with the Solium Infernum team; Google Stitch (as an example of image annotation).

---

## 6. Short quotes for the key claims

- "structurally, LLMs are bad at reading games. At least in their default state."
- "Games obviously have code, but there is a lot of other stuff that is not code."
- "key components of games that are effectively opaque to an LLM"
- "getting LLMs to work well with games is a context problem"
- "there is effectively 0 standardized tooling for anything"
- "the thing none of these do well is actually talk to your game."
- "We need to crack open the black box of your game"
- "naiively throwing screenshots at models can muddy their own sense of progress"
- "how easily can you save and load an exact state in your game?"
- "With a single object type, there is no ambiguity."
- "played back on a running instance of the game, no compiling required!"
- "the more you can drive your game to be able to make changes without compiling, the better."
- "It's all about trying to remove cycle bottlenecks."
- "The simulation is the source of truth"
- "What AI really likes it to work with text (and lots of it)"
- "an agentic turn can run through this WHOLE loop in seconds."
- "any game can easily be its own harness."
- Postscript: "I think the scale I'm targeting here is really larger projects."

---

## 7. Open questions, caveats and gaps for applying this to Godot

**Caveats from the article itself**
- Most of the advice is architectural and **works best when adopted at the start**. Retrofitting is described as very hard.
- The author **did not use any of this** on his current small project. The benefit grows with project size.
- The impact-assessment section is "narrow." Balance and test strategies are left to each game.
- The method is shown with a **C#/.NET** stack ("Plain C# (Best Language)," DLL simulation, dotMemory, polymorphic JSON in System.Text.Json) and Unity/Unreal profilers. The genres in his examples (Cantata, Monster Train, Solium Infernum) are turn-based or tactics games, which suit command/state architectures well. **[Inference]** It is less clear how well this fits real-time, physics-heavy games.

**Gaps that matter for Godot** (all **[Inference]**)
1. **Language and simulation boundary.** In Godot, "simulation in its own DLL" maps most directly to **Godot .NET (C#)** with a separate class library and a plain `dotnet test` project. For **GDScript**, you need another way to get the simulation out of the engine:
   - pure `RefCounted`/`Resource` classes with no `Node` or `SceneTree` dependency,
   - tests run headless (`godot --headless` with GUT or gdUnit4),
   - or a GDExtension/C++ library.

   Headless Godot still starts the engine, so the "VERY FAST" engine-free loop is weaker in pure GDScript.
2. **Scenes and resources (`.tscn`/`.tres`).** These are text, which helps compared with binary formats, but they are tied to the editor (UIDs, ExtResource/SubResource IDs, `.import` files). The article's answer is to keep logic and data out of scenes. Open question: how much should an agent edit `.tscn` directly, and how much should you generate scenes from data or code?
3. **Node/OOP versus the fat struct.** Godot's node tree and scene inheritance push toward the class-hierarchy style he warns against. Open question: a single `Thing` data struct in the simulation, with nodes as a dumb view that reconciles against state diffs. Who owns `Node` lifetimes and mapping IDs ("string target … is a big topic")?
4. **Determinism.**
   - Godot's global `randf()`/`randi()` must be replaced with one seeded `RandomNumberGenerator` (or `seed()` plus discipline).
   - Physics (`_physics_process`, Godot Physics or Jolt), variable `delta`, `Tween`/`AnimationPlayer` timing and threads are possible sources of non-determinism the article never mentions.
   - A fixed timestep and simulation-owned movement would be needed.
5. **Screenshots in practice.**
   - The slide's Godot snippet captures via `get_viewport().get_texture().get_image().save_png(...)`.
   - Headless runs (`--headless`) use a dummy renderer and **produce no images**. Agents need a real or virtual display (e.g. Xvfb) or `--write-movie` for frame capture.
   - Layer toggles map naturally to `CanvasLayer` visibility and render/visibility layers.
   - Fixed camera and fixed state are needed for odiff baselines to be stable.
6. **Command playback against a running instance.** Godot needs a way to inject commands into a live game: a file watcher, a TCP/WebSocket debug server, CLI user args (`-- --replay=file.json`), or the editor remote debugger. The article gives no transport.
7. **Profiling.** Godot's built-in profiler and Monitors are GUI tools, so the same problem applies. Text options: samply on the Godot binary or the .NET process, custom `Performance.get_monitor()` dumps to stdout or CSV, or `--print-fps`. Untested for agent use.
8. **Game feel, animation, audio, shaders.** None of the verification methods cover timing or feel. A Godot harness would need its own approach, e.g. recorded command replays with frame-captured clips, or numeric traces of positions and velocities over time.
9. **Claude Code integration.** The article doesn't say how to wire this into Claude Code: CLAUDE.md conventions, skills or custom commands that run replays, odiff and tests, hooks to auto-run checks, or an MCP bridge to the Godot editor. All of that is still to design.
10. **The "image diff as a progress metric" claim** is asserted, not shown with results. It works when a pixel-level target exists, such as a mockup or reference frame. For open-ended design changes, what is the target?
11. **The embedded talks** (Dreams, Monster Train, Solium Infernum) probably contain the detailed blackbox and fat-struct implementation guidance. I did not review them, and they are worth watching before committing to an architecture.
