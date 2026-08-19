from typing import List

def generate_appointment_id(existing_ids: List[str]) -> str:
    """
    Generates a unique and sequential appointment ID of the format APT-XXXXXX.
    Checks the list of existing IDs, finds the maximum numeric suffix, and increments it.
    """
    nums = []
    for app_id in existing_ids:
        if isinstance(app_id, str) and app_id.startswith("APT-"):
            try:
                num_part = app_id.split("-")[1]
                nums.append(int(num_part))
            except (IndexError, ValueError):
                pass
    next_num = max(nums) + 1 if nums else 1
    return f"APT-{next_num:06d}"

