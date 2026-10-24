from odoo import models, fields, api

class CrmNoteWizard(models.TransientModel):
    _name = 'crm.note.wizard'
    _description = 'CRM Note Wizard'

    date = fields.Datetime(string="Date", default=fields.Datetime.now,)
    salesperson_id = fields.Many2one('res.users', string="Salesperson")
    note = fields.Text(string="Note")

    lead_ids = fields.Many2many('crm.lead', string="Opportunities")

    # Filled automatically when the wizard is opened as a result of a stage
    # change (Kanban drag & drop, statusbar, API write, Automation Rule...).
    # When empty, the wizard behaves like a plain "Add Note" action.
    new_stage_id = fields.Many2one('crm.stage', string="New Stage")
    current_stage_id = fields.Many2one(
        'crm.stage', string="Current Stage",
        compute='_compute_current_stage_id',
    )

    @api.depends('lead_ids')
    def _compute_current_stage_id(self):
        for wizard in self:
            wizard.current_stage_id = wizard.lead_ids[:1].stage_id

    def action_add_note(self):
        """Create note lines for selected leads, then apply the pending
        stage change (if any) that triggered this wizard."""
        for lead in self.lead_ids:
            self.env['crm.note'].create({
                'lead_id': lead.id,
                # 'date': self.date,
                'salesperson_id': self.salesperson_id.id,
                'note': self.note,
            })

        if self.new_stage_id:
            self.lead_ids.with_context(skip_note_wizard=True).write({
                'stage_id': self.new_stage_id.id,
            })

        return {'type': 'ir.actions.act_window_close'}
    ###########################################################################
    @api.model
    def default_get(self, fields_list):
        """Set default salesperson from first selected lead"""
        res = super(CrmNoteWizard, self).default_get(fields_list)

        # Get lead_ids from either active_ids or default_lead_ids context
        lead_ids = []

        # Check if default_lead_ids is already set (from direct context)
        if 'lead_ids' in res and res['lead_ids']:
            # Extract IDs from the Many2many command format [(6, 0, [ids])]
            if isinstance(res['lead_ids'], list) and res['lead_ids'] and isinstance(res['lead_ids'][0], tuple):
                lead_ids = res['lead_ids'][0][2] if len(res['lead_ids'][0]) > 2 else []

        # If not, get from active_ids (when called from list/tree view)
        if not lead_ids:
            lead_ids = self.env.context.get('active_ids') or []

        if lead_ids:
            leads = self.env['crm.lead'].browse(lead_ids)
            if leads:
                res['lead_ids'] = [(6, 0, leads.ids)]
                res['salesperson_id'] = leads[0].user_id.id if leads[0].user_id else False

        return res
