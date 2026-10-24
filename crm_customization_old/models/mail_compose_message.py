from odoo import models, fields, api
import ast


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'
    # field to store selected CC partners
    cc_partners = fields.Many2many(
        'res.partner',
        'mail_compose_message_res_partner_cc_rel',  # relation table
        'wizard_id',  # column referring to wizard
        'partner_id',  # column referring to partner
        string="CC"
    )
    # field to store selected recipient partners
    recipient_partners = fields.Many2many(
        'res.partner',
        'mail_compose_message_res_partner_to_rel',  # relation table
        'wizard_id',  # column referring to wizard
        'partner_id',  # column referring to partner
        string="To"
    )
    # field to store generated CC email addresses
    cc_email = fields.Char(string="CC Emails")
    # method to update cc_email field when cc_partners field changes
    @api.onchange('cc_partners')
    def _onchange_cc_partners(self):
        emails = []
        for partner in self.cc_partners:
            if partner.email:
                emails.append(f'"{partner.name}" <{partner.email}>')
            # else:
            #     emails.append(partner.name)

        self.cc_email = ', '.join(emails)

    # override to include CC and To partners in mail values
    def _prepare_mail_values(self, res_ids):
        mail_values = super()._prepare_mail_values(res_ids)

        cc_email = self.cc_email
        recipient_partners = self.recipient_partners

        email_to_list = []
        partner_ids = []

        for partner in recipient_partners:
            if partner.email:
                email_to_list.append(f'"{partner.name}" <{partner.email}>')
            partner_ids.append(partner.id)  # always include partner_ids

        email_to = ', '.join(email_to_list)

        for res_id in res_ids:
            mail_values[res_id]['email_from'] = 'odoo@ellaithy.com.eg'

            # ensure at least one recipient exists
            if email_to:
                mail_values[res_id]['email_to'] = email_to
            if partner_ids:
                mail_values[res_id]['recipient_ids'] = [(6, 0, partner_ids)]
            if cc_email:
                mail_values[res_id]['email_cc'] = cc_email

        return mail_values

    # resend cancelled mails automatically
    def _action_send_mail(self, auto_commit=False):
        mails = super()._action_send_mail(auto_commit=auto_commit)

        if self.model == 'res.complaint' and self.res_ids:

            res_ids = ast.literal_eval(self.res_ids) if isinstance(self.res_ids, str) else self.res_ids

            # Use sudo() to bypass mail.mail access restriction for non-admin users
            created_mails = self.env['mail.mail'].sudo().search([
                ('model', '=', 'res.complaint'),
                ('res_id', 'in', res_ids),
                ('state', '=', 'cancelled')
            ])

            for mail in created_mails:
                mail.sudo().mark_outgoing()
                mail.sudo().send()

        return mails
#####################################################################
    # Override can_edit_body to always allow editing
    can_edit_body = fields.Boolean(
        compute='_compute_can_edit_body',
        store=False,
    )

    @api.depends('composition_mode', 'template_id')
    def _compute_can_edit_body(self):
        for record in self:
            record.can_edit_body = True  # Always editable

   #################################################################
    # method to default get to values from assign to field
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Pre-fill recipient_partners from context (assigned users)
        if self.env.context.get('default_recipient_partners'):
            res['recipient_partners'] = [(6, 0, self.env.context['default_recipient_partners'])]
        return res