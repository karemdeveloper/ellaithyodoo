{
    'name': 'Ellithy Helpdesk',
    'version': '1.0',
    'category': 'Helpdesk',
    'author': 'Ellithy Auto Group',
    'depends': ['helpdesk', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/email_templates.xml',
        'views/helpdesk_task_type.xml',
        'views/helpdesk_views.xml'
    ],
    'assets': {
        'web.assets_backend': [
            'ellithy_helpdesk/static/src/js/ticket_success_notification.js',
        ],
    },
    'installable': True
}
