# whoop-write-api v0.2.0 — SpotMe Integration Guide

## What Changed

### SportType enum
Use `SportType.WEIGHTLIFTING` instead of `sport_id=45`. All 80+ Whoop activity types available:

```python
from whoop import SportType

SportType.WEIGHTLIFTING  # 45
SportType.SAUNA          # 233
SportType.ICE_BATH       # 88
SportType.MEDITATION     # 70
SportType.STRETCHING     # 128
```

`sport_id` still accepts raw `int` — existing code passing `sport_id=45` works unchanged.

### Exercises are optional
`WorkoutWrite.exercises` now defaults to `None`. For non-weightlifting activities (sauna, meditation, etc.), omit exercises entirely:

```python
sauna = WorkoutWrite(
    sport_id=SportType.SAUNA,
    start="2026-03-16T18:00:00.000Z",
    end="2026-03-16T18:20:00.000Z",
)
result = await client.log_workout(sauna)
```

### WorkoutResult replaces dict
`log_workout()` now returns a `WorkoutResult` dataclass instead of a dict.

Before (v0.1):
```python
result = await client.log_workout(workout)
activity_id = result["activity_id"]
```

After (v0.2):
```python
result = await client.log_workout(workout)
activity_id = result.activity_id
linked = result.exercises_linked
error = result.error  # None on success, error string on partial failure
```

### Partial failure handling
If the workout is created but exercise linking fails, `log_workout()` now returns the `activity_id` instead of raising. Check `result.error`:

```python
result = await client.log_workout(workout)
if result.error:
    # workout exists on whoop but exercises weren't linked
    queue_retry(result.activity_id, workout.exercises)
```

### Dynamic sport type lookup
```python
types = await client.get_sport_types()
for t in types:
    print(f"{t.name}: {t.id}")
```

## whoop_service.py Changes Needed

1. Replace `result["activity_id"]` with `result.activity_id`
2. Handle `result.error` for the sync queue (partial failures no longer raise)
3. Optionally use `SportType` enum for readability

## Coming in v0.3

- Journal entries (caffeine, alcohol, supplements, stress)
- Body measurement updates (weight)
- Workout notes/annotations
- These require mitmproxy endpoint capture first
