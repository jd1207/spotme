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
        lines = []
        for l in section.split('\n'):
            l = l.strip()
            if not l or l.startswith('#'):
                continue
            # skip status/metadata lines
            l_lower = l.lower()
            if any(kw in l_lower for kw in ['status:', 'completed', 'duration:', 'workout duration']):
                continue
            # strip markdown bold/emphasis and list markers
            l = l.lstrip('- ')
            l = l.replace('**', '').replace('*', '')
            # strip numbered prefixes (e.g. "1. ", "2. ")
            l = re.sub(r'^\d+\.\s*', '', l)
            # extract just exercise name from detailed entries
            # e.g. "Pull-ups: 5 sets (8,7,6,6,5 reps) - Bodyweight" → "Pull-ups 5 sets"
            colon_match = re.match(r'^([^:]+):\s*(.+)$', l)
            if colon_match:
                name = colon_match.group(1).strip()
                detail = colon_match.group(2).strip()
                # extract set/rep scheme, drop parenthetical details and annotations
                scheme = re.match(r'(\d+\s*sets?\s*(?:x\s*[\d\-]+)?|\d+x[\d\-]+)', detail)
                if scheme:
                    l = f"{name} {scheme.group(1).strip()}"
                else:
                    l = name
            if l:
                lines.append(l)
        if lines:
            templates[day_type] = ', '.join(lines)
    return templates


def _parse_week_start_date(title: str) -> str | None:
    """extract a start date from week title like 'started 3/15' or 'Sun 3/22'"""
    from datetime import date as dt_date
    current_year = dt_date.today().year
    # "started M/D"
    m = re.search(r'started\s+(\d{1,2})/(\d{1,2})', title)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        return dt_date(current_year, month, day).isoformat()
    # "Sun M/D" or "M/D" as first date mention
    m = re.search(r'(?:Sun|Mon|Tue|Wed|Thu|Fri|Sat)\s+(\d{1,2})/(\d{1,2})', title)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        return dt_date(current_year, month, day).isoformat()
    return None


def _parse_weeks(content: str, schedule: dict, templates: dict) -> list:
    """parse ### Week N sections, merge recurring templates"""
    weeks = []
    week_pattern = re.compile(r'^### (Week \d+.*?)$', re.MULTILINE)
    matches = list(week_pattern.finditer(content))

    for i, match in enumerate(matches):
        title = match.group(1).strip()
        # strip markdown bold/emphasis and emoji artifacts
        title = title.replace('**', '').replace('*', '')
        title = re.sub(r'[✅❌⬜🔲]\s*', '', title).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[start:end].strip()

        items = []
        for line in body.split('\n'):
            line = line.strip()
            # strip markdown bold/emphasis from items too
            line = line.replace('**', '').replace('*', '')
            if line.startswith('- '):
                items.append(line[2:].strip())

        week_num_match = re.search(r'Week (\d+)', title)
        week_num = int(week_num_match.group(1)) if week_num_match else len(weeks) + 1

        # parse start date from title (e.g. "started 3/15" or "Sun 3/22")
        start_date = _parse_week_start_date(title)

        days = _build_days(schedule, templates, items)
        weeks.append({"number": week_num, "title": title, "days": days, "start_date": start_date})

    return weeks


def _build_days(schedule: dict, templates: dict, items: list) -> list:
    """build day list from schedule, templates, and week-specific items"""
    days = []
    visited_compound = set()
    matched_items: set[int] = set()

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

        for idx, item in enumerate(items):
            if idx in matched_items:
                continue
            item_lower = item.lower()
            type_first_word = day_type.lower().split()[0]
            if type_first_word not in item_lower:
                continue

            matched_items.add(idx)
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

    # second pass: assign unmatched items containing weight patterns to bench days
    unmatched = [items[i] for i in range(len(items)) if i not in matched_items]
    if unmatched:
        for item in unmatched:
            if not re.search(r'\d{2,3}x\d', item):
                continue
            for day in days:
                if 'bench' in day["type"].lower() and not day["planned"]:
                    day["planned"] = item
                    break

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
