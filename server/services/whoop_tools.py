import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


async def handle_create_activity(params, db):
    from server.services.whoop_service import get_whoop_client
    activity_type = params["activity_type"]
    duration = params.get("duration_minutes", 30)

    start = params.get("start_time")
    if not start:
        end = datetime.utcnow()
        start = (end - timedelta(minutes=duration)).isoformat() + "Z"

    end_time = params.get("end_time")
    if not end_time:
        end_time = (datetime.fromisoformat(start.replace("Z", "")) + timedelta(minutes=duration)).isoformat() + "Z"

    client = get_whoop_client(db)
    result = await client.create_activity(activity_type, start=start, end=end_time)
    return {"success": True, "activity_id": result.id}


async def handle_update_weight(params, db):
    from server.services.whoop_service import get_whoop_client
    weight_lbs = params["weight_lbs"]
    weight_kg = weight_lbs / 2.20462
    client = get_whoop_client(db)
    await client.update_weight(weight_kg)
    return {"success": True, "weight_kg": round(weight_kg, 1)}


async def handle_set_alarm(params, db):
    from server.services.whoop_service import get_whoop_client
    client = get_whoop_client(db)
    await client.set_alarm(params["time"], enabled=params.get("enabled", True))
    return {"success": True, "alarm_time": params["time"]}


async def handle_delete_activity(params, db):
    from server.services.whoop_service import get_whoop_client
    activity_id = params["activity_id"]
    is_recovery = params.get("is_recovery", False)
    client = get_whoop_client(db)
    await client.delete_activity(activity_id, is_recovery=is_recovery)
    return {"success": True, "deleted": activity_id}


async def handle_list_activities(params, db):
    from server.services.whoop_service import get_whoop_client
    limit = params.get("limit", 5)
    client = get_whoop_client(db)
    workouts = await client.get_workouts()
    activities = [{"id": w.id, "sport": w.sport_id, "start": str(w.start)} for w in workouts[:limit]]
    return {"success": True, "activities": activities}


async def handle_search_catalog(params, db):
    from server.models import ExerciseCatalog
    query = params["query"].lower()
    results = db.query(ExerciseCatalog).filter(
        ExerciseCatalog.name.ilike(f"%{query}%")
    ).limit(10).all()
    return {
        "success": True,
        "exercises": [{"id": r.whoop_id, "name": r.name, "equipment": r.equipment} for r in results],
    }


TOOL_HANDLERS = {
    "create_whoop_activity": handle_create_activity,
    "update_whoop_weight": handle_update_weight,
    "set_whoop_alarm": handle_set_alarm,
    "delete_whoop_activity": handle_delete_activity,
    "list_whoop_activities": handle_list_activities,
    "search_exercise_catalog": handle_search_catalog,
}


async def execute_whoop_tool(name, params, db):
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return {"error": f"unknown tool: {name}"}
    try:
        return await handler(params, db)
    except Exception as e:
        logger.warning("whoop tool %s failed: %s", name, e)
        return {"error": str(e)}
