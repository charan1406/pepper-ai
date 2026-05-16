---
tags: [system, autonomous, exploration]
---

# Autonomous Exploration Mode

## When This Activates
Pepper enters autonomous mode when:
- No person has been detected for 60 seconds
- No conversation is active
- Battery is above 30%
- Not currently charging

## What Happens

### Exploration Loop (runs every 3 seconds)

```
1. YOLO (CPU, continuous)
   └─ Detects objects in current camera view at 15fps
   └─ Maintains running object list with positions
   └─ Flags NEW objects (not seen in last scan)
   └─ Flags MISSING objects (were there, now gone)

2. When YOLO flags a change → triggers 4B vision
   └─ 4B receives camera frame + prompt:
      "Describe what you see. Focus on: new objects,
       people, text on screens/whiteboards, changes
       from the known room state."
   └─ 4B outputs structured observation (JSON)

3. 0.8B processes the observation
   └─ Compares against spatial_map.md
   └─ Compares against known_objects
   └─ Outputs change summary
   └─ Orchestrator writes to Obsidian vault

4. Optional: Pepper slowly rotates head to scan room
   └─ HeadYaw sweeps: -1.5 → 0 → 1.5 → 0 (cycle)
   └─ Each position triggers a new YOLO frame
   └─ Full room scan in ~15 seconds

5. Optional: Pepper navigates to unexplored areas
   └─ Only if has_map = True
   └─ Moves to areas not recently scanned
   └─ Maps new objects to absolute positions
```

### What Gets Written to the Vault

#### New Object Detected
→ Appended to `environment/known_objects.md`
```markdown
- **blue backpack**: first seen 2026-05-15 14:30, position near [[locations/desk_john|John's desk]], confidence: 0.87
```

#### Object Moved/Gone
→ Updated in `environment/known_objects.md`
```markdown
- **coffee cup**: ~~position desk_john~~ → no longer visible as of 14:45
```

#### Person Seen (not interacted with)
→ Logged in `environment/observations.md`
```markdown
- 14:32: [[people/unknown_003|Unknown #003]] seen near [[locations/meeting_table|meeting table]], did not approach Pepper
```

#### Environment Change
→ Logged in `environment/observations.md` with backlinks
```markdown
- 14:35: [[locations/whiteboard|Whiteboard]] content changed — now has equations (previously empty)
```

#### Routine Detection (over days)
→ Updated in `environment/routines.md`
```markdown
- [[people/john_smith|John]] typically arrives between 8:45-9:15
- Coffee machine area is busiest 10:00-10:30
- Lab is usually empty after 18:00
```

## Interruption Protocol

When a person is detected during autonomous mode:
1. IMMEDIATELY stop head scanning
2. IMMEDIATELY stop navigation
3. Turn head toward detected person
4. Switch to conversation mode
5. Fast brain greets them within 200ms
6. Log: "Autonomous mode interrupted by [person] at [time]"

Resume autonomous mode 60 seconds after person leaves.

## Resource Sharing

During autonomous mode:
- 4B: processes one vision frame every 3-5 seconds (not continuous)
- 0.8B: processes observation summaries (fast, tiny context)
- YOLO: runs continuously regardless (CPU, doesn't compete)
- face_recognition: runs every 3 seconds (CPU)

When conversation starts:
- 4B: immediately available for conversation (drops vision task)
- 0.8B: immediately available for filler/greeting
- Vision frame processing is paused until idle again
