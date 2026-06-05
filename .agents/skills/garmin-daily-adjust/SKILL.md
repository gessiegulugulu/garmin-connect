---
name: garmin-daily-adjust
description: Review yesterday's Garmin training and today's recovery, then adjust only today's row in the active seven-day TRAINING_PLAN.md. Use for morning check-ins, deciding what to train today, adapting today's session after yesterday's workload, or reducing/increasing today's plan based on recovery.
---

# Garmin Daily Adjust

1. Read `memory.md`, `.agents/training-system.md`, and `TRAINING_PLAN.md`.
2. Fetch yesterday's activities and enough detail to understand duration, intensity, and trained movement patterns. Fetch today's sleep summary, Body Battery, resting heart rate/stress, and recent HRV trend when available.
3. Compare yesterday's actual work with yesterday's planned row. Mark that row `完成` or note the discrepancy if it is still present in the active plan.
4. Classify today's readiness as good, mixed, or poor using trends rather than one number.
5. Adjust only today's row unless moving today's session necessarily requires one explicit swap with another day. Preserve the rest of the plan.
6. Choose among keeping the session, reducing sets/duration/RPE, replacing it with recovery work, swapping location-compatible sessions, or resting.
7. Append a timestamped note to the plan's adjustment record.
8. Archive only the training and recovery review to `history/YYYY-MM/daily-review-YYYY-MM-DD.md`. Keep plan change details only in `TRAINING_PLAN.md`.
9. Tell the user what changed, why, and what signs should cause them to stop or further reduce training.

Do not convert ordinary wearable variation into a medical claim. If there is no active plan, create only a sensible plan for today and instruct the user to run `$garmin-weekly-plan` for a full week.
