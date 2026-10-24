from odoo import models, fields, api



class CrmNote(models.Model):
    _name = 'crm.note'
    _description = 'CRM Note'

    lead_id = fields.Many2one('crm.lead', string="Opportunity")
    date = fields.Datetime(string="Date", default=fields.Datetime.now)
    salesperson_id = fields.Many2one('res.users', string="Salesperson", )
    note = fields.Text(string="Note")


    #####################################################################
    @api.onchange('lead_id')
    def _onchange_lead_id(self):
        """Automatically set salesperson from the linked opportunity"""
        if self.lead_id:
            self.salesperson_id = self.lead_id.user_id




