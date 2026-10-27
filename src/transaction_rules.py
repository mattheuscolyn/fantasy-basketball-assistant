"""Describe ESPN daily transaction limits, without predicting approval."""

def transaction_settings(settings, days_in_matchup=7):
    raw = settings.get("acquisitionSettings") or {}
    per_day = raw.get("matchupLimitPerScoringPeriod") is True
    units = raw.get("matchupAcquisitionLimit")
    count = int(units) if type(units) in (int, float) and units >= 0 and int(units) == units else None
    return {
        "system": raw.get("acquisitionType"),
        "daily_limit_enabled": per_day,
        "per_scoring_period": count if per_day else None,
        "per_matchup": count if not per_day else None,
        "maximum_matchup_additions": count * days_in_matchup if per_day and count is not None else count,
        "season_limit": None if raw.get("acquisitionLimit") == -1 else raw.get("acquisitionLimit"),
        "waiver_hours": raw.get("waiverHours") if type(raw.get("waiverHours")) is int else None,
        "waiver_process_hour": raw.get("waiverProcessHour") if type(raw.get("waiverProcessHour")) is int else None,
        "waiver_process_days": raw.get("waiverProcessDays") if isinstance(raw.get("waiverProcessDays"), list) else None,
        "daily_usage_known": False,
        "caution": "Transactions already made today and individual player clearance must be checked in ESPN.",
    }
