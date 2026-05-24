{
    "name": "IBS API Integration",
    "summary": "Enterprise-grade API Integration for Odoo",
    "description": """
        Connect your Odoo instance with external systems through a robust API:
        * Secure endpoints with token authentication
        * JSON data exchange
        * Comprehensive resource access
        * Configurable model exposure
        * Detailed documentation
    """,
    "version": "18.0",
    "category": "Technical/Integration",
    "license": "LGPL-3",
    "author": "ibs",
    "website": "https://ibs-egy.com/",
    "depends": ["base", "web"],
    "data": [
        "security/ir.model.access.csv",
    ],
    "application": False,
    "installable": True,
    "auto_install": False,
    "external_dependencies": {
        "python": ["requests"],
    },
}