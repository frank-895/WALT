from datetime import UTC, datetime, timedelta
from typing import Any

from api.demo.models import DemoBrief

SECTORS = {
    "technology": "information-technology",
    "professional-services": "industrials",
    "financial-services": "financials",
    "healthcare": "health-care",
    "retail": "consumer-discretionary",
    "manufacturing": "industrials",
    "other": "communication-services",
}
COMPANY_SIZES = {"1-10": 10, "11-50": 50, "51-250": 250, "251-500": 500, "500+": 500}
DEAL_AMOUNTS = {
    "1-10": 12_000,
    "11-50": 35_000,
    "51-250": 80_000,
    "251-500": 140_000,
    "500+": 240_000,
}
PRIORITY_LABELS = {
    "pipeline-visibility": "clear pipeline visibility",
    "follow-up": "consistent customer follow-up",
    "lead-organization": "better lead organisation",
    "deal-prioritization": "faster deal prioritisation",
    "team-coordination": "stronger team coordination",
    "reporting": "simpler reporting",
}


def generate_seed(brief: DemoBrief, now: datetime | None = None) -> dict[str, Any]:
    """Generate a complete fictional Atomic database from a compact visitor brief.

    Args:
        brief: Validated visitor and company context.
        now: Stable clock value for tests.

    Returns:
        A database object accepted by Atomic's FakeRest data provider.
    """
    current_time = (now or datetime.now(UTC)).astimezone(UTC)
    created_at = _timestamp(current_time - timedelta(days=30))
    updated_at = _timestamp(current_time)
    visitor_first_name, visitor_last_name = _split_name(brief.visitor_name)
    priority_summary = ", ".join(PRIORITY_LABELS[item] for item in brief.priorities)
    base_amount = DEAL_AMOUNTS[brief.team_size]

    companies = [
        _company(
            0,
            brief.company_name,
            SECTORS[brief.industry],
            COMPANY_SIZES[brief.team_size],
            f"Visitor company interested in {priority_summary}.",
            created_at,
            2,
            2,
        ),
        _company(
            1,
            "BrightPath Labs",
            "information-technology",
            50,
            "Product team evaluating a wider CRM rollout.",
            created_at,
            1,
            1,
        ),
        _company(
            2,
            "Northstar Works",
            "industrials",
            250,
            "Growing account with several stakeholder groups.",
            created_at,
            1,
            1,
        ),
    ]
    contacts = [
        _contact(
            0,
            visitor_first_name,
            visitor_last_name,
            "Operations Lead",
            0,
            brief.company_name,
            "hot",
            f"Wants {priority_summary}.",
            created_at,
            updated_at,
            2,
        ),
        _contact(
            1,
            "Jordan",
            "Bell",
            "Revenue Director",
            0,
            brief.company_name,
            "warm",
            "Focused on adoption and measurable outcomes.",
            created_at,
            updated_at,
            1,
        ),
        _contact(
            2,
            "Mia",
            "Chen",
            "VP Sales",
            1,
            "BrightPath Labs",
            "warm",
            "Requested a rollout plan.",
            created_at,
            updated_at,
            1,
        ),
        _contact(
            3,
            "Theo",
            "Martin",
            "Commercial Lead",
            2,
            "Northstar Works",
            "cold",
            "New inbound opportunity.",
            created_at,
            updated_at,
            1,
        ),
    ]
    deals = [
        _deal(
            0,
            f"{brief.company_name} CRM rollout",
            0,
            [0, 1],
            "proposal-sent",
            base_amount,
            priority_summary,
            created_at,
            updated_at,
            current_time + timedelta(days=21),
            0,
        ),
        _deal(
            1,
            f"{brief.company_name} expansion",
            0,
            [0],
            "opportunity",
            base_amount // 2,
            "Potential follow-on team rollout.",
            created_at,
            updated_at,
            current_time + timedelta(days=45),
            0,
        ),
        _deal(
            2,
            "BrightPath annual plan",
            1,
            [2],
            "in-negociation",
            base_amount + 18_000,
            "Commercial terms under review.",
            created_at,
            updated_at,
            current_time + timedelta(days=14),
            0,
        ),
        _deal(
            3,
            "Northstar discovery",
            2,
            [3],
            "opportunity",
            max(8_000, base_amount // 3),
            "Discovery call booked with the commercial team.",
            created_at,
            updated_at,
            current_time + timedelta(days=35),
            1,
        ),
    ]
    tasks = [
        _task(
            0,
            0,
            "follow-up",
            f"Send examples focused on {PRIORITY_LABELS[brief.priorities[0]]}",
            current_time + timedelta(days=1),
        ),
        _task(
            1,
            0,
            "demo",
            "Run the tailored Atomic CRM demo",
            current_time + timedelta(days=2),
        ),
        _task(
            2, 1, "email", "Share rollout milestones", current_time + timedelta(days=3)
        ),
        _task(
            3, 2, "call", "Review commercial terms", current_time + timedelta(days=1)
        ),
        _task(
            4,
            3,
            "meeting",
            "Complete discovery session",
            current_time + timedelta(days=5),
        ),
    ]
    contact_notes = [
        {
            "id": 0,
            "contact_id": 0,
            "text": f"Primary goals: {priority_summary}.",
            "date": updated_at,
            "sales_id": 0,
            "status": "hot",
        },
        {
            "id": 1,
            "contact_id": 2,
            "text": "Team responded positively to the first walkthrough.",
            "date": _timestamp(current_time - timedelta(days=2)),
            "sales_id": 0,
            "status": "warm",
        },
    ]
    deal_notes = [
        {
            "id": 0,
            "deal_id": 0,
            "text": "Tailored demo is the agreed next step.",
            "date": updated_at,
            "sales_id": 0,
        },
        {
            "id": 1,
            "deal_id": 2,
            "text": "Waiting on final procurement feedback.",
            "date": _timestamp(current_time - timedelta(days=1)),
            "sales_id": 0,
        },
    ]
    return {
        "companies": companies,
        "contacts": contacts,
        "contact_notes": contact_notes,
        "deals": deals,
        "deal_notes": deal_notes,
        "sales": [
            {
                "id": 0,
                "user_id": "0",
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane@example.test",
                "administrator": True,
                "disabled": False,
            }
        ],
        "tags": [],
        "tasks": tasks,
        "configuration": [{"id": 1, "config": {}}],
    }


def _company(
    company_id: int,
    name: str,
    sector: str,
    size: int,
    description: str,
    created_at: str,
    contact_count: int,
    deal_count: int,
) -> dict[str, Any]:
    """Build one Atomic company record."""
    return {
        "id": company_id,
        "name": name,
        "logo": {"src": "", "title": name},
        "sector": sector,
        "size": size,
        "linkedin_url": "",
        "website": "",
        "phone_number": "",
        "address": "",
        "zipcode": "",
        "city": "",
        "state_abbr": "",
        "sales_id": 0,
        "created_at": created_at,
        "description": description,
        "revenue": "",
        "tax_identifier": "",
        "country": "",
        "context_links": [],
        "nb_contacts": contact_count,
        "nb_deals": deal_count,
    }


def _contact(
    contact_id: int,
    first_name: str,
    last_name: str,
    title: str,
    company_id: int,
    company_name: str,
    status: str,
    background: str,
    first_seen: str,
    last_seen: str,
    task_count: int,
) -> dict[str, Any]:
    """Build one Atomic contact record."""
    return {
        "id": contact_id,
        "first_name": first_name,
        "last_name": last_name,
        "title": title,
        "company_id": company_id,
        "company_name": company_name,
        "email_jsonb": [
            {"email": f"{first_name.lower()}@example.test", "type": "Work"}
        ],
        "phone_jsonb": [],
        "avatar": {},
        "linkedin_url": None,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "has_newsletter": False,
        "tags": [],
        "gender": "",
        "sales_id": 0,
        "status": status,
        "background": background,
        "nb_tasks": task_count,
    }


def _deal(
    deal_id: int,
    name: str,
    company_id: int,
    contact_ids: list[int],
    stage: str,
    amount: int,
    description: str,
    created_at: str,
    updated_at: str,
    closing_date: datetime,
    index: int,
) -> dict[str, Any]:
    """Build one Atomic deal record."""
    return {
        "id": deal_id,
        "name": name,
        "company_id": company_id,
        "contact_ids": contact_ids,
        "category": "other",
        "stage": stage,
        "description": description,
        "amount": amount,
        "created_at": created_at,
        "updated_at": updated_at,
        "expected_closing_date": closing_date.date().isoformat(),
        "sales_id": 0,
        "index": index,
    }


def _task(
    task_id: int, contact_id: int, task_type: str, text: str, due_date: datetime
) -> dict[str, Any]:
    """Build one Atomic task record."""
    return {
        "id": task_id,
        "contact_id": contact_id,
        "type": task_type,
        "text": text,
        "due_date": _timestamp(due_date),
        "done_date": None,
        "sales_id": 0,
    }


def _split_name(name: str | None) -> tuple[str, str]:
    """Return a safe two-part fictional contact name."""
    parts = (name or "Alex Morgan").split(maxsplit=1)
    return parts[0], parts[1] if len(parts) > 1 else "Morgan"


def _timestamp(value: datetime) -> str:
    """Render a datetime as an Atomic-compatible UTC timestamp."""
    aware_value = (
        value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    )
    return aware_value.isoformat().replace("+00:00", "Z")
