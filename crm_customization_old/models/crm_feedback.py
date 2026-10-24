from odoo import models, fields, api
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo import fields as ofields


class CrmFeedback(models.Model):
    _name = 'crm.feedback'
    _description = 'CRM Feedback'

    lead_id = fields.Many2one('crm.lead', string="Opportunity")
    date = fields.Datetime(string="Date", default=fields.Datetime.now)
    salesperson_id = fields.Many2one('res.users', string="Salesperson", )
    feedback = fields.Text(string="Feedback")
    feedback2 = fields.Selection([
        ('not_contacted', 'Not contacted'),
        ('answered', 'Answered'),
        ('no_answer', 'No answer – Phone off'),
        ('wrong_number', 'Wrong number'),
        ('callback_required', 'Callback required'),
    ], string="Feedback")

    #####################################################################
    @api.onchange('lead_id')
    def _onchange_lead_id(self):
        """Automatically set salesperson from the linked opportunity"""
        if self.lead_id:
            self.salesperson_id = self.lead_id.user_id


########################################################################
    @api.model
    def create(self, vals):
        record = super(CrmFeedback, self).create(vals)
        # لما يتضاف feedback جديد، خلي has_feedback = True
        if record.lead_id:
            record.lead_id.has_feedback = True
        return record

########################################################################
# @api.model
# def create(self, vals):
#     rec = super(CrmFeedback, self).create(vals)
#     # send a bus notification so JS ticker stops for the lead
#     try:
#         feedback_date = rec.date or fields.Datetime.now()
#         # tuple: (dbname, channel)
#         channel = 'sla_channel'
#         payload = {'lead_id': rec.lead_id.id, 'feedback_date': feedback_date}
#         # sendone is available in most Odoo versions
#         self.env['bus.bus'].sendone((self._cr.dbname, channel), payload)
#     except Exception:
#         # don't break feedback creation if bus fails
#         pass
#     return rec
