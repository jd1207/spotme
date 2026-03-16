VALID_COMPONENT_TYPES = {
    "header", "stat_card", "exercise_card", "set_logger",
    "rest_timer", "text_block", "video_prompt", "chart",
    "action_button", "chat_bubble",
}

def validate_layout(layout_data) -> dict:
    if not isinstance(layout_data, dict):
        return {"valid": False, "error": "layout must be a dict", "layout": None}
    if "screen" not in layout_data:
        return {"valid": False, "error": "missing 'screen' field", "layout": None}
    if "layout" not in layout_data or not isinstance(layout_data["layout"], list):
        return {"valid": False, "error": "missing or invalid 'layout' array", "layout": None}
    filtered = [
        component for component in layout_data["layout"]
        if isinstance(component, dict) and component.get("type") in VALID_COMPONENT_TYPES
    ]
    return {"valid": True, "error": None, "layout": {"screen": layout_data["screen"], "layout": filtered}}
