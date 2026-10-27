"""Count real ESPN additions applied during this fantasy matchup."""
from src.weekly import scoring_period


def transaction_counts(espn_fetch, week, today, team_ids):
    """Executed ADD items only; deduplicate by ESPN transaction ID.

    Any API failure makes counts unverified. Never present a guessed remaining
    allowance as fact. Pending claims aren't deducted until executed.
    """
    known = set()
    counts = {str(team): 0 for team in team_ids}
    pending = {str(team): 0 for team in team_ids}
    for date in week:
        if date > today:
            break
        period = scoring_period(date)
        response = espn_fetch(["mTransactions2"], scoring_period=period)
        transactions = response.get("transactions")
        if not isinstance(transactions, list):
            raise ValueError("ESPN transactions missing or malformed.")
        for row in transactions:
            if not isinstance(row, dict):
                continue
            if row.get("scoringPeriodId") != period:
                continue
            team = str(row.get("teamId"))
            if team not in counts:
                continue
            if row.get("type") == "FUTURE_ROSTER":
                continue
            additions = sum(
                1 for item in row.get("items") or []
                if isinstance(item, dict) and item.get("type") == "ADD"
            )
            if not additions:
                continue
            tx_id = row.get("id")
            # An absent stable transaction ID means we cannot safely dedupe.
            if not tx_id:
                raise ValueError("An ESPN ADD transaction has no unique ID.")
            if tx_id in known:
                continue
            known.add(tx_id)
            status = row.get("status")
            if status == "EXECUTED":
                counts[team] += additions
            elif status in ("PENDING", "PROPOSED"):
                pending[team] += additions
    return {
        "executed_additions_by_team": counts,
        "pending_claims_by_team": pending,
        "source": "ESPN executed transaction items scoped to this matchup",
        "verified": True,
    }
