DEFAULT_RATES = {
    "Analyst": 2800,
    "Architect": 5200,
    "Backend Developer": 3600,
    "Frontend Developer": 3400,
    "QA Engineer": 2600,
    "DevOps Engineer": 3800,
    "Project Manager": 3200,
    "UX/UI Designer": 3000,
    "Support Engineer": 2400,
}


class PricingService:
    def normalize_rates(self, raw_rates: list[dict]) -> dict[str, float]:
        rates = dict(DEFAULT_RATES)
        for item in raw_rates:
            rates[item["role"]] = float(item["hourly_rate"])
        return rates

    def effort_budget(self, tasks: list[dict], rates: dict[str, float]) -> dict:
        total_hours = 0
        total_cost = 0.0
        by_role: dict[str, dict] = {}
        for task in tasks:
            for estimate in task["estimates"]:
                role = estimate["role"]
                hours = estimate["hours"]
                cost = hours * rates.get(role, 3000)
                total_hours += hours
                total_cost += cost
                bucket = by_role.setdefault(role, {"hours": 0, "cost": 0})
                bucket["hours"] += hours
                bucket["cost"] += round(cost, 2)
        return {"total_hours": total_hours, "total_cost": round(total_cost, 2), "by_role": by_role}

    def support_budget(self, scheme: str, rates: dict[str, float]) -> dict:
        hourly = rates.get("Support Engineer", 2400)
        if scheme == "third_line_business_hours":
            monthly_hours = 8 * 5 * 4
            title = "3 line support, 06:00-18:00 workdays"
        else:
            monthly_hours = 24 * 365 / 12 * 3
            title = "1/2/3 line support, 24x7x365"
        monthly_cost = monthly_hours * hourly
        return {
            "scheme": scheme,
            "title": title,
            "monthly_hours": round(monthly_hours, 2),
            "monthly_cost": round(monthly_cost, 2),
            "annual_cost": round(monthly_cost * 12, 2),
        }

    def warranty_budget(self, development_cost: float) -> dict:
        return {"percent": 8, "annual_cost": round(development_cost * 0.08, 2)}

    def monthly_expenses(self, development_cost: float, warranty_cost: float, months: int) -> list[dict]:
        development_month = development_cost / months
        warranty_month = warranty_cost / 12
        return [
            {
                "month": month,
                "development": round(development_month, 2),
                "warranty_reserve": round(warranty_month, 2),
                "total": round(development_month + warranty_month, 2),
            }
            for month in range(1, months + 1)
        ]
