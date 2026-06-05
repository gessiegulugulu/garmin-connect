---
name: garmin-health-chat
description: Analyze and discuss physical condition, recovery, sleep, stress, fatigue, exercise response, and other health-related questions using relevant Garmin data. Use for open-ended conversations such as why the user feels tired, whether recovery looks normal, how recent habits may relate to symptoms, or what Garmin trends suggest; do not use for creating or editing a structured training plan.
---

# Garmin Health Chat

1. Read `memory.md` and `.agents/training-system.md` from the repository root.
2. Clarify the user's actual question from conversation context. Do not fetch every metric by default.
3. Query the smallest useful Garmin dataset:
   - Sleep or morning fatigue: sleep summary, Body Battery, resting heart rate, stress, and 7- to 21-day HRV trend.
   - Training fatigue: recent activities plus recovery metrics.
   - Longer trends: use date-range or weekly summary endpoints.
4. Compare current values with the user's recent baseline. Separate observations, plausible explanations, uncertainty, and practical next steps.
5. Answer conversationally in the user's language. State that wearable data cannot diagnose disease when medical causes are possible.
6. Archive a compact summary under the current month only when Garmin data materially informed the answer. Do not archive casual conversation with no data query.

Keep recommendations conservative and compatible with the user's health and posture goals. Mention urgent warning signs only when relevant; do not flood routine answers with generic disclaimers.
