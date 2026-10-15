scenario_noautoload: scenario_min without `[autoload]` (AC-05.13: `h run` -> rc 2 `[run.not-synced]`).
Owner: A5/T5. Scenario jump.json is schema-valid so the not-synced pre-check is what fires. No scripts.
Expected `h check`: PASS. Never import the repo copy (B3).
