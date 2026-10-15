# R1.7 Rendering and screenshots in a container (Godot 4.7-stable, headless Linux)

## Answer
- Most reliable recipe: `xvfb-run -a godot --path P --rendering-method gl_compatibility --rendering-driver opengl3 --fixed-fps 60 ...`, capturing with `get_viewport().get_texture().get_image().save_png()` after `await RenderingServer.frame_post_draw`. In the 3D and 2D tests below, same binary + same renderer + same container gave byte-identical PNGs across two runs. [Run: results table]
- `--headless` CANNOT be used for screenshots. It uses the dummy renderer, and `frame_post_draw` never fires, so the script hangs forever (two processes had to be killed). [Run: `godot --headless --path proj -- --mode=static --n=1` hung until killed]
- Software rendering works with no GPU. Mesa llvmpipe provides GL 4.5 out of the box. [Run: `renderer=llvmpipe (LLVM 20.1.2, 256 bits) api=4.5 (Core Profile) Mesa 25.2.8`] Vulkan (forward_plus/mobile) needs `apt-get update && apt-get install -y mesa-vulkan-drivers vulkan-tools mesa-utils` (lavapipe). apt worked in this container. Without it, Godot silently falls back to OpenGL3 even if you ask for forward_plus/mobile. [Run: `ERROR: Required Vulkan instance extension VK_KHR_surface not found` then `WARNING: Your video card drivers seem not to support the required Vulkan version, switching to OpenGL 3`] After install: `Vulkan 1.4.318 - Forward+ - Using Device #0: Unknown - llvmpipe`.
- Non-determinism comes from wall-clock delta, not from the renderer. Unseeded CPUParticles2D without `--fixed-fps` differed run-to-run (0-1 of 30 frames identical, roughly 7-13 pixels, 0.01% of the frame). With `--fixed-fps 60`, 30/30 frames were identical, even unseeded. Always pass `--fixed-fps` and also set `use_fixed_seed`/`seed` on particles.
- `--write-movie` with `--fixed-fps 30 --quit-after 60` gave 60 PNGs, and 60/60 were byte-identical across two runs. It took about 0.8 s wall for 320x240 gl_compatibility. Best for short frame sequences when the scene needs no per-frame script logic.
- Diff tool: odiff 4.5.0 (the native binary, `node_modules/@odiff/linux-x64/odiff`) with `--parsable-stdout`. Gate on the exit code (0 same, 22 differs) and on the pixel count. Use ImageMagick `compare -metric AE` (pixel count) and `RMSE` as a fallback and for the sub-threshold drift odiff hides. Recommended thresholds are in section 5.
- GL and Vulkan renders of the same scene are NOT identical. The background differs by 1 level (25 vs 26 on the red channel), which is 74,957 pixels by IM AE. odiff `-t 0.01` and above calls them equal. Pin one renderer per baseline set.

## 1. Environment facts
- Container: 4 cores, Ubuntu 24.04, Mesa 25.2.8. Preinstalled: xvfb-run, libGL, swrast/kms_swrast DRI, libvulkan1, ImageMagick. Not preinstalled: glxinfo, vulkaninfo, any Vulkan ICD. [Run: `which glxinfo vulkaninfo` returned nothing, `/usr/share/vulkan/icd.d` was absent]
- Installed by me: `apt-get update; apt-get install -y mesa-vulkan-drivers vulkan-tools mesa-utils`. The proxy allowed archive.ubuntu.com (HTTP 200). `apt-get update` is needed first, because the package list was stale ("no installation candidate").
- After install, `glxinfo -B`: llvmpipe GL 4.5 compat. `vulkaninfo --summary`: apiVersion 1.4.318, deviceName llvmpipe (lvp). [Run]
- Godot 4.7.stable.official.5b4e0cb0f. ALSA errors appear on stderr and are harmless (falls back to the dummy audio driver). Add `--audio-driver Dummy` to silence them [Unverified].

## 2. Working recipe
Setup (once): import the project so resources exist: `godot --headless --path P --import` (this works headless, since it needs no rendering).

Capture command (Compatibility renderer, the most portable):
```
xvfb-run -a -s "-screen 0 640x480x24" godot --path P \
  --rendering-method gl_compatibility --rendering-driver opengl3 \
  --fixed-fps 60 -- --out=/abs/out --mode=static --n=1
```
Forward+/Mobile (needs lavapipe, see above): replace the flags with `--rendering-method forward_plus --rendering-driver vulkan` (or `mobile`). Note that `forward_plus` + `opengl3` is rejected: `Invalid renderer/driver combination 'forward_plus' and 'opengl3', aborting.` [Run]

Capture script (tested; the user args after `--` are read with `OS.get_cmdline_user_args()`):
```gdscript
# after building/arranging the scene and (optionally) advancing N frames:
await RenderingServer.frame_post_draw
var img := get_viewport().get_texture().get_image()
img.save_png(out + "/f%03d.png" % i)                       # full frame
img.get_region(Rect2i(10, 90, 100, 60)).save_png(out + "/crop.png")   # region crop
```
Layer toggling (tested):
- 2D: set `canvas_layer.visible = false`, then `await RenderingServer.frame_post_draw` and capture. HUD (CanvasLayer) with Label vs without: odiff `374;0.49` (374 px, 0.49%). [Run]
- 3D: set `camera.cull_mask = 1` (or 2) and capture again. Objects on VisualInstance3D `layers` 1 and 2: all vs layer1-only gave odiff `604;0.79`. all/layer1/layer2 gave three different hashes. [Run]
- Always `await RenderingServer.frame_post_draw` between a visibility change and the next capture, otherwise you get the previous frame (the change is only applied on the next draw) [Unverified for the no-await case; I always awaited].
- Region cropping: `Image.get_region(Rect2i)` produced a 100x60 PNG as expected. [Run: `identify crop.png` gave `PNG 100x60`] Cropping before saving is the cheapest way to focus a diff on one panel. odiff can also mask regions at diff time with `-i x1:y1-x2:y2` (ignoring the HUD region gave `0` differences). [Run]
- Note: running a bare script with `--scene res://x.gd` fails (`Failed loading scene: res://cull.gd`). The scene argument must be a .tscn. [Run]

Movie mode (frame sequence without any script capture code):
```
xvfb-run -a godot --path P --rendering-method gl_compatibility --rendering-driver opengl3 \
  --write-movie /abs/out/m.png --fixed-fps 30 --quit-after 60 -- <user args>
```
Outputs `m00000000.png ... m00000059.png` plus `m.wav` (62 files). Log: `60 frames at 30 FPS (movie length: 00:00:02:00), recorded in 00:00:00 (200% of real-time speed).` [Run] `--quit-after` counts frames: 60 gave exactly 60 PNGs. [Run]

## 3. Repeatability results (each case run twice in fresh processes, `cmp` on every frame)
Test scene: 320x240 viewport, ColorRect background and moving sprite, a CanvasLayer Label, and optionally CPUParticles2D (50 particles) or a rotating lit BoxMesh in 3D.

| Case | Renderer / driver | Frames | Identical A vs B | Notes |
|---|---|---|---|---|
| static 2D | gl_compatibility / opengl3 | 1 | 1/1 | |
| static 2D | forward_plus / vulkan (lavapipe) | 1 | 1/1 | |
| moving sprite (frame-driven) | gl_compat | 30 | 30/30 | |
| moving sprite | forward_plus | 30 | 30/30 | |
| moving sprite | mobile | 30 | 30/30 | |
| CPUParticles2D, no seed, no fixed-fps | gl_compat | 30 | 1/30 | 7-13 px differ (0.01%); IM RMSE ~0.008 |
| same | forward_plus | 30 | 0/30 | |
| CPUParticles2D, `use_fixed_seed`, no fixed-fps | gl_compat | 30 | 30/30 | |
| CPUParticles2D, no seed, `--fixed-fps 60` | gl_compat | 30 | 30/30 | |
| CPUParticles2D, seed + fixed-fps | gl_compat, forward_plus | 30 | 30/30 | |
| 3D rotating cube + DirectionalLight | gl_compat | 10 | 10/10 | |
| 3D cube | forward_plus | 10 | 10/10 | |
| 3D cube, `viewport.use_taa = true` | forward_plus | 10 | 10/10 | TAA gave identical output run-to-run in this frame-driven test. Only 10 frames and a simple scene, so treat as weak evidence. |
| 3D cube | mobile | 10 | 10/10 | |
| write-movie, seeded particles, fixed-fps 30 | gl_compat | 60 | 60/60 | |
| GL vs Vulkan, same 3D scene | gl_compat vs forward_plus | 1 | NOT equal | IM AE 74,957 px, RMSE 0.0022; background 25 vs 26 (red). forward_plus vs mobile: AE 0 (identical). |

Takeaways: animation determinism depends on how time advances. Frame-driven changes are exact; anything driven by real delta (particles, tweens, `_process(delta)` accumulators) is not, unless you pass `--fixed-fps`. GPUParticles, shaders using TIME, AnimationPlayer, MSAA, SSAO/SDFGI/glow and similar effects were NOT tested [Unverified].

## 4. Timing (4 cores, llvmpipe, 320x240)
| Step | Time |
|---|---|
| Whole process, gl_compatibility, 1 capture | ~0.6-1.9 s wall (0.6 s warm) |
| Whole process, forward_plus/mobile 2D | ~0.7-3.0 s wall |
| In-script `get_image()` + `save_png()` per frame, 2D | ~2.5-3.5 ms (one 12.8 ms outlier) |
| 30 frames captured in script, gl_compat | ~200 ms of script time |
| 3D cube, 10 frames, gl_compat / mobile / forward_plus | 0.8 s / 4.5 s / 7.4-8.1 s script time, dominated by first-frame pipeline and shader compilation on llvmpipe. Per-frame capture cost after the first was ~2.5 ms |
| write-movie, 60 frames 2D | ~0.8 s wall total |
| odiff on 320x240 | 3-11 ms |
Per-frame cost scales with resolution and renderer, so measure at your target size. I tested only 320x240.

## 5. Diffing
odiff 4.5.0 output formats [Run]:
- Default: `Found 374 different pixels (0.49%)` and exit code 22; exit 0 when identical (prints nothing or `0`).
- `--parsable-stdout`: `374;0.49` (pixel count; percent), or `0` when identical. Optional `--output-diff-lines` / `--output-diff-cols` append comma-separated line and column indexes.
- Third argument writes a diff PNG. Other flags: `-t/--threshold` (0.0-1.0, default 0.1), `--aa`, `-i/--ignore x1:y1-x2:y2`, `--fail-on-layout` (exit 21).
- Gotcha: the default threshold 0.1 is color-distance based and very lenient. It treated GL vs Vulkan as identical (0 px) at `-t 0.01` and up, and only `-t 0` found 74,957 px (97.6%). It did not flag a 1/255 shift.
- Gotcha: with different image sizes, odiff reports a large percentage (full vs 100x60 crop: `72559;94.48`) rather than failing, unless `--fail-on-layout`. Always pass `--fail-on-layout` for baselines.
- Gotcha: install via `npm i odiff-bin`, which pulls `@odiff/linux-x64`. Call the native binary `node_modules/@odiff/linux-x64/odiff` directly. One earlier invocation through the `node_modules/.bin` wrapper (plus `--help`) hung my shell; I could not reproduce it with `--version` under `timeout`, so always wrap in `timeout` and redirect stdin from /dev/null. The root cause is [Unverified]. The Node API (`odiff-bin` compare()) was not completed; the attempt used a missing `/usr/bin/time` and was not rerun.
- ImageMagick fallback: `compare -metric AE a.png b.png null:` prints the differing pixel count (`406`). `-metric RMSE` prints `2693.69 (0.041103)`. Output goes to stderr, and exit code is 1 for different, 0 for similar, 2 for error (the exit code was not checked) [Unverified]. AE counts ANY difference, including 1-level shifts, so it is stricter than odiff's default.

Recommended thresholds (my judgment, based on the numbers above):
- Same binary + same renderer + `--fixed-fps` + seeded randomness: require exact equality (`cmp`, or odiff `-t 0` count == 0). In the tests above that held for every deterministic case.
- Behavioural/regression check across rendering paths or when particles are unseeded: odiff `-t 0.1 --aa --fail-on-layout --parsable-stdout`, fail if the diff is above 0.1% of pixels (the unseeded particle noise was 0.01%; the HUD toggle was 0.49%, so a real change stays visible).
- Use IM `RMSE` normalised (the value in parentheses) as a secondary gauge: ~0.002 for GL-vs-Vulkan background drift, ~0.009 for particle noise, 0.02-0.04 for real element changes in this scene.
- Never mix GL and Vulkan baselines.

## 6. Limitations
- No `--headless` screenshots (hang). A display server (Xvfb) is required; Xvfb adds ~0.3-1 s startup.
- Software rendering only: this container has no GPU, so GPU-specific rendering (driver bugs, performance, vsync) cannot be judged. llvmpipe results may differ from real GPUs and across Mesa versions, so baselines are only valid for the same Mesa/LLVM build.
- Vulkan on Xvfb works via lavapipe once installed, and needs root apt access, which a locked-down CI may lack.
- Audio is not verifiable (dummy driver). Window decorations, the OS cursor, and native dialogs are not in the viewport image. Editor UI was not tested.
- Not tested: 4K or large viewports, stretch modes, MSAA, HDR/glow/SSAO, GPUParticles, AnimationPlayer, C# builds, SubViewport capture, and `Window` embedding.
- First run on a fresh project needs `--import`, otherwise resource loading may fail [Unverified for this exact case; I ran the import first].

## Blocked sources
None. No web sources were fetched; all claims are from runs on the 4.7 binary. odiff came from npm (OK). apt archive.ubuntu.com worked.

## Open questions
- Does TAA stay deterministic with real camera motion and longer sequences (only 10 frames of a spinning cube tested)?
- Is GPUParticles2D/3D deterministic under llvmpipe with a seed and fixed-fps?
- Does `--write-movie` match `get_image()` capture byte-for-byte (not compared)?
- Does odiff's Node API work cleanly in CI (not completed)?
- Working files: /tmp/claude-0/-home-user/77c17b82-ea72-5e78-90c8-1959b76a4dc3/scratchpad/research/r1_7_work/ (proj/main.gd, proj/cull.gd, run.sh, out/).
