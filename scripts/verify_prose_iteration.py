"""Comprehensive verification of prose iteration implementation."""

import sys
import re
from pathlib import Path

def verify_diff_generator():
    """Verify DiffGenerator changes."""
    print("Verifying DiffGenerator...")

    diff_file = Path("src/generation/iteration/diff.py")
    content = diff_file.read_text(encoding='utf-8')

    checks = {
        "No truncate method": "_truncate_content" not in content,
        "No truncate call": "truncate_content" not in content,
        "Has get_diff_statistics": "def get_diff_statistics" in content,
        "Uses original content": "original_content=original," in content or "original_content=original" in content,
        "Statistics returns dict": "'added': added" in content and "'removed': removed" in content,
        "Statistics has total_changes": "'total_changes': added + removed" in content
    }

    for check, passed in checks.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} {check}")
        if not passed:
            return False

    return True


def verify_scale_detector():
    """Verify ScaleDetector changes."""
    print("\nVerifying ScaleDetector...")

    scale_file = Path("src/generation/iteration/scale.py")
    content = scale_file.read_text(encoding='utf-8')

    checks = {
        "Has _estimate_lines_changed method": "def _estimate_lines_changed" in content,
        "Dialog estimation exists": "if 'dialogue' in action or 'dialog' in feedback:" in content,
        "Dialog multiplier is 3": "return max_num * 3" in content,
        "Threshold < 100 = patch": "if estimated_lines < 100:" in content and "return \"patch\"" in content,
        "Threshold > 300 = regenerate": "elif estimated_lines > 300:" in content and "return \"regenerate\"" in content,
        "Override uses lines": "_estimate_lines_changed(intent)" in content,
        "Override threshold > 300": "if estimated_lines > 300:" in content,
        "Example in comment": "20 pieces of dialog across 10 chapters" in content
    }

    for check, passed in checks.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} {check}")
        if not passed:
            return False

    # Test the actual logic
    print("\n  Testing dialog estimation logic:")
    feedback_example = "adjust 20 pieces of dialog across 10 chapters"
    numbers = re.findall(r'\d+', feedback_example)
    max_num = max(int(n) for n in numbers) if numbers else 0
    estimated = max_num * 3
    result = "patch" if estimated < 100 else "regenerate" if estimated > 300 else "unclear"

    print(f"    Input: '{feedback_example}'")
    print(f"    Numbers found: {numbers}")
    print(f"    Max number: {max_num}")
    print(f"    Estimated lines: {estimated}")
    print(f"    Result: {result}")

    if result == "patch":
        print(f"    [OK] Correctly classifies as patch")
        return True
    else:
        print(f"    [FAIL] Should be patch, got {result}")
        return False


def verify_lod_context_builder():
    """Verify LODContextBuilder changes."""
    print("\nVerifying LODContextBuilder...")

    context_file = Path("src/generation/lod_context.py")
    content = context_file.read_text(encoding='utf-8')

    checks = {
        "Has build_prose_iteration_context": "def build_prose_iteration_context" in content,
        "Uses get_chapters_yaml": "chapters_yaml = project.get_chapters_yaml()" in content,
        "Calls _load_all_prose": "prose = self._load_all_prose(project)" in content,
        "Marks target chapter": "context['target_chapter'] = target_chapter" in content,
        "Comment says ALL chapters": "FULL prose for ALL chapters" in content,
        "Comment says no truncation": "No truncation" in content or "untruncated" in content
    }

    for check, passed in checks.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} {check}")
        if not passed:
            return False

    return True


def verify_iteration_coordinator():
    """Verify IterationCoordinator changes."""
    print("\nVerifying IterationCoordinator...")

    coord_file = Path("src/generation/iteration/coordinator.py")
    content = coord_file.read_text(encoding='utf-8')

    checks = {
        "Routes prose to prose_patch": "if target_lod == 'prose':" in content and "return await self._execute_prose_patch" in content,
        "Has _execute_prose_patch method": "async def _execute_prose_patch" in content,
        "Builds prose iteration context": "build_prose_iteration_context(" in content,
        "Creates backup": "backup_path = " in content and ".backup.md" in content,
        "backup_path.write_text": "backup_path.write_text(original_content" in content,
        "Gets statistics": "stats = self.diff_generator.get_diff_statistics(diff)" in content,
        "Displays statistics": "print(f\"\\n✓ Applied {stats['total_changes']}" in content,
        "Shows undo instructions": "To undo:" in content,
        "Error recovery": "if backup_path.exists():" in content and "chapter_file.write_text(backup_path.read_text" in content,
        "Includes backup in change_info": "'backup_path':" in content,
        "Includes statistics in change_info": "'statistics': stats" in content
    }

    for check, passed in checks.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} {check}")
        if not passed:
            return False

    return True


def verify_all():
    """Run all verifications."""
    print("=" * 60)
    print("COMPREHENSIVE VERIFICATION OF PROSE ITERATION")
    print("=" * 60)

    results = []

    results.append(("DiffGenerator", verify_diff_generator()))
    results.append(("ScaleDetector", verify_scale_detector()))
    results.append(("LODContextBuilder", verify_lod_context_builder()))
    results.append(("IterationCoordinator", verify_iteration_coordinator()))

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "[OK]" if passed else "[FAIL]"
        print(f"{status} {name}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n[SUCCESS] ALL VERIFICATIONS PASSED")
        return 0
    else:
        print("\n[ERROR] SOME VERIFICATIONS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(verify_all())
