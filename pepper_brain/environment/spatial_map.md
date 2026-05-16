---
last_exploration: 
map_file: 
room_size: "8m x 6m approximately"
tags: [environment, spatial, map]
---

# Lab Room — Spatial Map

## Landmarks
- **[[locations/entrance|Entrance door]]**: (0.0, 0.0) — main entry point
- **[[locations/charging_station|Charging station]]**: (0.5, 0.5) — Pepper's home position
- **[[locations/coffee_machine|Coffee machine]]**: (0.5, 5.0) — left wall
- **[[locations/whiteboard|Whiteboard]]**: (4.0, 5.5) — back wall
- **[[locations/meeting_table|Meeting table]]**: (3.0, 3.0) — center of room
- **[[locations/fanuc_arm|Fanuc robot arm]]**: (7.0, 0.5) — right side, near entrance

## People's Usual Positions
- (No data yet — positions will be learned from face detection over time)

## Zones
- **Entrance area**: (0-1, 0-1) — high traffic
- **Work desks**: (5-7, 1-4) — right side of room
- **Meeting area**: (2-4, 2-4) — center
- **Equipment zone**: (6-8, 0-1) — Fanuc arm, do not navigate here

## Navigation Notes
- Floor is smooth and flat — good for omni-wheel movement
- Watch for cables near desks
- Meeting area chairs may be moved — re-scan periodically
