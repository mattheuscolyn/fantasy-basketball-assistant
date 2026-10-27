"""Normalize ESPN matchup acquisition rules; period scaling is not a daily cap."""


def transaction_settings(settings, days_in_matchup=7):
    raw = settings.get("acquisitionSettings") or {}
    scaled = raw.get("matchupLimitPerScoringPeriod") is True
    quantity = raw.get("matchupAcquisitionLimit")
    unit = int(quantity) if type(quantity) in (int, float) and quantity >= 0 and int(quantity) == quantity else None
    maximum = unit * days_in_matchup if scaled and unit is not None else unit
    return {
        "system": raw.get("acquisitionType"),
        "matchup_limit_scaled_by_days": scaled,
        "per_scoring_period_multiplier": unit if scaled else None,
        "per_matchup": maximum,
        "maximum_matchup_additions": maximum,
        "season_limit": None if raw.get("acquisitionLimit") == -1 else raw.get("acquisitionLimit"),
        "waiver_hours": raw.get("waiverHours") if type(raw.get("waiverHours")) is int else None,
        "waiver_process_hour": raw.get("waiverProcessHour") if type(raw.get("waiverProcessHour")) is int else None,
        "waiver_process_days": raw.get("waiverProcessDays") if isinstance(raw.get("waiverProcessDays"), list) else None,
        "usage_verified": False,
        "caution": "Completed additions count against the matchup limit; check pending claims and player clearance in ESPN.",
    }
