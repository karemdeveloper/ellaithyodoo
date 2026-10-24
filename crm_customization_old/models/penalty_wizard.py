from odoo import models, fields, api

class CrmPenaltyWizard(models.TransientModel):
    _name = 'crm.penalty.wizard'
    _description = 'CRM Penalty Report Wizard'

    branch_id = fields.Many2one('res.branch', string="Branch", required=True)
    date_from = fields.Date(string="Date From", required=True)
    date_to = fields.Date(string="Date To", required=True)

    def action_print_report(self):
        """Generate the penalty report"""
        data = {
            'branch_id': self.branch_id.id,
            'branch_name': self.branch_id.branch_name,
            'date_from': self.date_from,
            'date_to': self.date_to,
        }
        return self.env.ref('crm_customization.action_crm_penalty_pdf_report').report_action(self, data=data)
