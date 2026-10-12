{
    "name": "CRM Marketing - Importable",
    "summary": "CRM marketing dashboard, monthly performance analysis, and marketing cost management",
    "version": "18.0.16.0.0",
    "category": "Sales/CRM",
    "author": "Ahmed Karem",
    "license": "LGPL-3",
    "depends": ["base", "web", "crm", "utm", "base_import_module"],
    "data": [
        "models/compare_models.xml",
        "security/compare_security.xml",
        "security/ir.model.access.csv",
        "views/compare_cost_views.xml",
        "views/compare_merge_views.xml",
        "views/compare_configuration_views.xml",
        "views/compare_dashboard_action.xml",
        "views/compare_menus.xml"
    ],
    "assets": {
        "web.assets_backend": [
            "compare_module_importable/static/src/js/dynamic_source_field.js",
            "compare_module_importable/static/src/js/sales_access_dashboard.js",
            "compare_module_importable/static/src/js/compare_dashboard.js",
            "compare_module_importable/static/src/xml/dynamic_source_field.xml",
            "compare_module_importable/static/src/xml/compare_dashboard.xml",
            "compare_module_importable/static/src/xml/sales_access_dashboard.xml",
            "compare_module_importable/static/src/scss/compare_dashboard.scss"
        ]
    },
    "application": True,
    "installable": True,
    "auto_install": False
}
