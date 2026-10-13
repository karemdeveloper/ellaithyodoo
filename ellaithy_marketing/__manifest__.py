{
    'name': 'Ellaithy Marketing Analytics (Python)',
    'version': '18.0.2.0.0',
    'category': 'Marketing',
    'summary': 'Python-powered marketing analytics, CRM attribution, costs and source groups',
    'author': 'Ellaithy',
    'license': 'LGPL-3',
    'depends': ['base', 'web', 'crm', 'utm'],
    'data': [
        'security/marketing_security.xml',
        'security/ir.model.access.csv',
        'views/marketing_views.xml',
        'views/marketing_menus.xml',
    ],
    'assets': {'web.assets_backend': [
        'ellaithy_marketing/static/src/js/marketing_dashboard.js',
        'ellaithy_marketing/static/src/js/marketing_compare.js',
        'ellaithy_marketing/static/src/xml/marketing_dashboard.xml',
        'ellaithy_marketing/static/src/xml/marketing_compare.xml',
        'ellaithy_marketing/static/src/scss/marketing_dashboard.scss',
    ]},
    'application': True,
    'installable': True,
}
