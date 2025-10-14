"""Helper script to update chapters.py for scene-based system."""
import re
from pathlib import Path

file_path = Path('D:/Personal/Projects/AgenticAuthor/src/generation/chapters.py')
content = file_path.read_text(encoding='utf-8')

# Phase 1: Rename variables and parameters (order matters - most specific first)
replacements = [
    # Method parameters and local variables
    ('events_per_chapter: List[int]', 'scenes_per_chapter: List[int]'),
    ('events_per_chapter[', 'scenes_per_chapter['),
    ('total_events', 'total_scenes'),
    ('base_we', 'base_ws'),
    ('events_distribution', 'scenes_distribution'),
    ('act_we', 'act_ws'),
    ('batch_events', 'batch_scenes'),

    # Method calls to DepthCalculator
    ('DepthCalculator.distribute_events_across_chapters', 'DepthCalculator.distribute_scenes_across_chapters'),
    ('DepthCalculator.get_act_words_per_event', 'DepthCalculator.get_act_words_per_scene'),

    # Comments and display text
    ('words-per-event', 'words-per-scene'),
    ('words per event', 'words per scene'),
    ('words/event', 'words/scene'),
    ('w/e ', 'w/s '),
    (' w/e', ' w/s'),
]

for old, new in replacements:
    content = content.replace(old, new)

file_path.write_text(content, encoding='utf-8')
print(f"✓ Phase 1 complete: Renamed variables and method calls")
print(f"  - events_per_chapter → scenes_per_chapter")
print(f"  - total_events → total_scenes")
print(f"  - base_we → base_ws")
print(f"  - act_we → act_ws")
print(f"  - Method calls updated to use scene terminology")
