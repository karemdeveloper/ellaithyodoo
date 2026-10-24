from odoo import models, api

class CrmPenaltyReport(models.AbstractModel):
    _name = 'report.crm_customization.crm_penalty_pdf_template'
    _description = 'CRM Penalty Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        branch_id = data.get('branch_id')
        date_from = data.get('date_from')
        date_to = data.get('date_to')

        branch = self.env['res.branch'].browse(branch_id)

        leads = self.env['crm.lead'].search([
            ('branch_name', '=', branch_id),
            ('create_date', '>=', date_from),
            ('create_date', '<=', date_to),
        ])

        result = {}
        for lead in leads:
            salesperson = lead.user_id.name or 'No Salesperson'

            if salesperson not in result:
                result[salesperson] = {str(i): 0 for i in range(0, 10)}
                result[salesperson]['late'] = 0
                result[salesperson]['total'] = 0
                result[salesperson]['salesperson'] = salesperson

            ld = max(0, int(lead.late_days or 0))
            if ld >= 10:
                result[salesperson]['late'] += 1
                result[salesperson]['total'] += 1
            elif ld > 0:
                result[salesperson][str(ld)] += 1
                result[salesperson]['total'] += 1


        docs = list(result.values())

        return {
            'doc_ids': docids,
            'doc_model': 'crm.penalty.wizard',
            'docs': docs,
            'branch_name': branch.branch_name or '',
            'date_from': date_from,
            'date_to': date_to,
        }
