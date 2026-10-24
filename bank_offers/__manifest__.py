{
    "name": "Bank Offers",
    "version": "18.0.1.4.0",
    "summary": "Python custom addon for bank financing programs, pre-assessment, installment calculation and bank recommendations",
    "description": """
Bank Offers for Odoo 18
=======================
- Maintain bank financing programs, rates, insurance and sale-ban fees.
- Pre-assess customers using income, job, age, vehicle price and down payment.
- Calculate installments automatically.
- Recommend the three most suitable and fastest eligible financing offers.
- Separate user and configuration-manager permissions.
    """,
    "category": "Sales/CRM",
    "author": "Ellaithy",
    "license": "LGPL-3",
    "depends": ["base", "mail", "web"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "security/rules.xml",
        "data/sequence.xml",
        "data/initial_data.xml",
        "data/bank_priority.xml",
        "data/backfill_imported_rates.xml",
        "views/bank_views.xml",
        "views/program_views.xml",
        "views/job_type_views.xml",
        "views/assessment_views.xml",
        "views/menu_views.xml",
        "reports/bank_offer_report.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
