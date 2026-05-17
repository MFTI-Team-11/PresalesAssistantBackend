class ReportService:
    def render(self, presale, payload: dict) -> str:
        lines = [
            f"# Presale report: {presale.title}",
            "",
            f"Customer: {presale.customer_name or 'not specified'}",
            "",
            "## Architecture",
        ]
        lines.extend(f"- {item['name']}: {item['description']}" for item in payload["architecture_options"])
        lines.extend(
            [
                "",
                "## Budget",
                f"- Development: {payload['effort_budget']['total_cost']}",
                f"- Warranty: {payload['warranty_budget']['annual_cost']}",
                f"- Support annual: {payload['support_budget']['annual_cost']}",
                "",
                "## Monthly expenses",
            ]
        )
        lines.extend(f"- Month {item['month']}: {item['total']}" for item in payload["monthly_expenses"])
        lines.extend(["", "## Risks"])
        lines.extend(f"- {item['risk']}: {item['mitigation']}" for item in payload["risks"])
        return "\n".join(lines)
