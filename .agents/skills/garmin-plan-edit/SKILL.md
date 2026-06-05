---
name: garmin-plan-edit
description: Modify the active seven-day TRAINING_PLAN.md from conversational requirements such as schedule changes, gym or pool availability, soreness, preferred exercises, travel, time limits, or a request to replace a session. Use when the user wants to change an existing plan without performing a full weekly review.
---

# Garmin Plan Edit

1. Read `memory.md`, `.agents/training-system.md`, and `TRAINING_PLAN.md`.
2. Extract explicit constraints and preferences from the current conversation. Ask only when the requested change is genuinely ambiguous or unsafe to infer.
3. Decide whether Garmin data is needed. Do not query it for a simple calendar or exercise substitution; query recent recovery only when the reason involves fatigue, soreness, illness, or training load.
4. Modify the smallest affected portion of the plan. Preserve unaffected dates, completed status, overall seven-day range, and useful notes.
5. Maintain training balance and recovery spacing after substitutions. Respect home, gym, and pool availability from `memory.md`.
6. Add a timestamped adjustment note describing the user's request and the resulting change.
7. Do not create a plan-change file in `history`. Keep the change record only in `TRAINING_PLAN.md`.
8. Report the changed dates and sessions concisely.

If no active plan exists, do not invent a full week under this skill. Direct the user to `$garmin-weekly-plan`, unless the request clearly concerns only today's session.
