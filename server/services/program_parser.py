import re

DAY_ORDER = ["Fri", "Sat", "Sun", "Mon", "Tue", "Wed", "Thu"]
ABBREV_MAP = {
    "Monday": "Mon", "Tuesday": "Tue", "Wednesday": "Wed",
    "Thursday": "Thu", "Friday": "Fri", "Saturday": "Sat",
    "Sunday": "Sun", "Tue or Wed": "Tue/Wed",
}


def parse_program(content: str) -> dict:
    """parse training plan markdown into structured weeks with days"""
    schedule = _parse_schedule(content)
    templates = _parse_templates(content, schedule)
    weeks = _parse_weeks(content, schedule, templates)
    progression = _extract_progression(weeks)
    return {"weeks": weeks, "progression": progression}


def _get_section(content: str, title_pattern: str) -> str:
    """extract content of a ## section by title pattern"""
    pattern = re.compile(
        rf'^## .*{title_pattern}.*$', re.MULTILINE | re.IGNORECASE
    )
    match = pattern.search(content)
    if not match:
        return ""
    start = match.end()
    next_section = re.search(r'^## ', content[start:], re.MULTILINE)
    end = start + next_section.start() if next_section else len(content)
    return content[start:end].strip()


def _parse_schedule(content: str) -> dict:
    """parse ## Weekly Schedule into {day_abbrev: type}"""
    section = _get_section(content, "Weekly Schedule")
    schedule = {}
    for line in section.split('\n'):
        line = line.strip().lstrip('- ')
        # strip markdown bold/emphasis markers
        line = line.replace('**', '').replace('*', '')
        if not line:
            continue
        day_pattern = '|'.join(ABBREV_MAP.keys())
        match = re.match(
            rf'({day_pattern})[:\s]+(.+?)(?:\s*[—\-\(].*)?$',
            line, re.IGNORECASE,
        )
        if match:
            day_name = match.group(1).strip()
            workout_type = match.group(2).strip().rstrip(' —-')
            abbrev = ABBREV_MAP.get(day_name, day_name[:3])
            schedule[abbrev] = workout_type
    return schedule


def _parse_templates(content: str, schedule: dict) -> dict:
    """extract recurring day templates from ## sections"""
    templates = {}
    for day_type in schedule.values():
        candidates = [
            re.escape(day_type.split('/')[0].strip()),
            re.escape(day_type.split()[0]),
        ]
        first_word = day_type.split()[0]
        if first_word.endswith('s'):
            candidates.append(re.escape(first_word[:-1]))
        section = ""
        for candidate in candidates:
            section = _get_section(content, candidate)
            if section:
                break
        if not section:
            continue
        lines = [
            l.strip().lstrip('- ')
            for l in section.split('\n')
            if l.strip() and not l.strip().startswith('#')
        ]
        if lines:
            templates[day_type] = ', '.join(lines)
    return templates


def _parse_weeks(content: str, schedule: dict, templates: dict) -> list:
    """parse ### Week N sections, merge recurring templates"""
    weeks = []
    week_pattern = re.compile(r'^### (Week \d+.*?)$', re.MULTILINE)
    matches = list(week_pattern.finditer(content))

    for i, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[start:end].strip()

        items = []
        for line in body.split('\n'):
            line = line.strip()
            if line.startswith('- '):
                items.append(line[2:].strip())

        week_num_match = re.search(r'Week (\d+)', title)
        week_num = int(week_num_match.group(1)) if week_num_match else len(weeks) + 1
        days = _build_days(schedule, templates, items)
        weeks.append({"number": week_num, "title": title, "days": days})

    return weeks


def _build_days(schedule: dict, templates: dict, items: list) -> list:
    """build day list from schedule, templates, and week-specific items"""
    days = []
    visited_compound = set()

    for day_abbrev in DAY_ORDER:
        day_type = schedule.get(day_abbrev, "")
        actual_abbrev = day_abbrev

        if not day_type:
            for key, val in schedule.items():
                if day_abbrev in key and key not in visited_compound:
                    actual_abbrev = key
                    day_type = val
                    visited_compound.add(key)
                    break

        if not day_type:
            continue

        planned = templates.get(day_type, "")
        note = ""
        status = "upcoming"

        for item in items:
            item_lower = item.lower()
            type_first_word = day_type.lower().split()[0]
            if type_first_word not in item_lower:
                continue

            colon_idx = item.find(':')
            raw = item[colon_idx + 1:].strip() if colon_idx > 0 else item

            if 'completed' in item_lower:
                completed_idx = item_lower.find('completed')
                period_idx = item.rfind('.', 0, completed_idx)
                if period_idx > colon_idx:
                    planned = item[colon_idx + 1:period_idx].strip()
                    note = item[period_idx + 1:].strip()
                else:
                    planned = raw.split('COMPLETED')[0].split('completed')[0]
                    planned = planned.rstrip('. ')
                    note = item[completed_idx:].strip()
                status = "completed"
            else:
                planned = raw
            break

        days.append({
            "day_of_week": actual_abbrev,
            "type": day_type,
            "planned": planned,
            "note": note,
            "status": status,
        })

    return days


def _extract_progression(weeks: list) -> list:
    """extract heaviest weight per week for bench progression chart"""
    progression = []
    for w in weeks:
        max_weight = 0
        for day in w.get("days", []):
            weights = re.findall(r'(\d{2,3})x\d+', day.get("planned", ""))
            for wt in weights:
                val = int(wt)
                if val > max_weight:
                    max_weight = val
        if max_weight > 0:
            progression.append({
                "week": w["number"],
                "weight": max_weight,
                "label": f"W{w['number']}",
            })
    return progression
