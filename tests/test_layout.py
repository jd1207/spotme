from server.services.layout_service import validate_layout, VALID_COMPONENT_TYPES

def test_valid_layout():
    layout = {
        "screen": "workout_session",
        "layout": [
            {"type": "header", "title": "Bench Day", "subtitle": "Recovery: 85%"},
            {"type": "exercise_card", "name": "Bench Press", "sets": 5, "reps": 3, "weight": 235},
        ],
    }
    result = validate_layout(layout)
    assert result["valid"] is True
    assert len(result["layout"]["layout"]) == 2

def test_unknown_components_dropped():
    layout = {
        "screen": "dashboard",
        "layout": [
            {"type": "header", "title": "Test"},
            {"type": "invented_widget", "foo": "bar"},
            {"type": "stat_card", "label": "Recovery", "value": "82%"},
        ],
    }
    result = validate_layout(layout)
    assert result["valid"] is True
    assert len(result["layout"]["layout"]) == 2

def test_completely_invalid_layout():
    result = validate_layout("not json")
    assert result["valid"] is False

def test_missing_screen_field():
    layout = {"layout": [{"type": "header", "title": "Test"}]}
    result = validate_layout(layout)
    assert result["valid"] is False

def test_all_component_types_recognized():
    expected = {"header", "stat_card", "exercise_card", "set_logger", "rest_timer", "text_block", "video_prompt", "chart", "action_button", "chat_bubble"}
    assert VALID_COMPONENT_TYPES == expected
