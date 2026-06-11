import phonenumbers
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Override user_id to set default to current user
    user_id = fields.Many2one(
        'res.users',
        string='Salesperson',
        # default=lambda self: self.env.user,
        tracking=True,
        help="The internal user in charge of this contact."
    )

    branch_id = fields.Many2one('res.branch', string="Branch")
    area_id = fields.Many2one('res.area', string="Area")
    company_custom_id = fields.Many2one('res.company.custom', string="Company")
    is_opportunity = fields.Boolean(string='Is Opportunity', default=False)
    survey_ids = fields.One2many('res.survey', 'partner_id', string="Surveys")
    crm_source_id = fields.Many2one('res.source', string="Source", required=True)

    # Indexed to speed up duplicate-phone lookups (_compute_customer_already_exist),
    # which does a full search('phone', '=', ...)
    phone = fields.Char(index=True)

    # Stored & indexed normalized (E.164) representations of phone/mobile,
    # used by _check_duplicate_phone to do an indexed DB lookup instead of
    # loading and re-parsing every contact in the database.
    phone_normalized = fields.Char(string="Phone (Normalized)", compute="_compute_normalized_phones", store=True, index=True)
    mobile_normalized = fields.Char(string="Mobile (Normalized)", compute="_compute_normalized_phones", store=True, index=True)

    def action_open_create_opportunity_wizard(self):
        """Open the wizard popup"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Create Opportunity',
            'res_model': 'opportunity.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_id': self.id},
        }

    #############################################################################################

    def action_create_survey(self):
        """Create a new survey for this customer and open it"""
        self.ensure_one()
        survey = self.env['res.survey'].create({
            'partner_id': self.id,  # Customer name automatically filled
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.survey',
            'res_id': survey.id,
            'view_mode': 'form',
            'target': 'current',
        }

    #########################################################################################
    survey_count = fields.Integer(string="Survey Count", compute="_compute_survey_count")

    def _compute_survey_count(self):
        for rec in self:
            rec.survey_count = self.env['res.survey'].search_count([('partner_id', '=', rec.id)])

    def action_view_survey(self):
        """View all surveys linked to this customer"""
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("crm_customization.action_res_survey")
        action['domain'] = [('partner_id', '=', self.id)]
        action['context'] = {'default_partner_id': self.id}
        return action

    #########################################################################################

    @api.constrains('phone', 'mobile')
    def _check_phone_length(self):
        """Validate that phone numbers have at least 11 digits"""
        for record in self:
            if record.phone:
                phone_digits = ''.join(filter(str.isdigit, record.phone))
                if len(phone_digits) < 11:
                    raise ValidationError(
                        f'Phone number must contain at least 11 digits. Current: {len(phone_digits)} digits'
                    )
            
            if record.mobile:
                mobile_digits = ''.join(filter(str.isdigit, record.mobile))
                if len(mobile_digits) < 11:
                    raise ValidationError(
                        f'Mobile number must contain at least 11 digits. Current: {len(mobile_digits)} digits'
                    )

    @api.onchange('area_id')
    def _onchange_area_id(self):
        for rec in self:
            rec.branch_id = rec.area_id.branch_area.id if rec.area_id else False

    def _normalize_phone(self, number, default_region='EG'):
        if not number:
            return False
        try:
            parsed = phonenumbers.parse(number, default_region)
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except Exception:
            pass
        return ''.join(filter(str.isdigit, number))

    @api.depends('phone', 'mobile')
    def _compute_normalized_phones(self):
        for rec in self:
            rec.phone_normalized = rec._normalize_phone(rec.phone) or False
            rec.mobile_normalized = rec._normalize_phone(rec.mobile) or False

    @api.constrains('phone', 'mobile')
    def _check_duplicate_phone(self):
        """Validate that phone and mobile are unique across all contacts (country-code aware)"""
        for rec in self:
            normalized = [n for n in [rec.phone_normalized, rec.mobile_normalized] if n]

            if not normalized:
                continue

            duplicate = self.sudo().search([
                ('id', '!=', rec.id),
                '|', ('phone_normalized', 'in', normalized), ('mobile_normalized', 'in', normalized),
            ], limit=1)

            if duplicate:
                raise ValidationError(
                    _('Phone number already exists for contact: %s') % duplicate.display_name
                )

    ###################################################################################################################

    complaint_count = fields.Integer(
        string='Complaints',
        compute='_compute_complaint_count'
    )

    def _compute_complaint_count(self):
        for partner in self:
            partner.complaint_count = self.env['res.complaint'].search_count([
                ('customer_id', '=', partner.id)
            ])

    def action_create_complaint(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Create Complaint',
            'res_model': 'res.complaint.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_customer_id': self.id,'defult_state': 'under_investigate'},
        }

    def action_view_complaint(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Complaints',
            'res_model': 'res.complaint',
            'view_mode': 'list,form',
            'domain': [('customer_id', '=', self.id)],
            'target': 'current',
        }
    #######################################################################################

    customer_already_exist_id = fields.Many2one(
        'res.partner',
        string="Customer Already Exist",
        compute="_compute_customer_already_exist",
        store=False
    )
    
    # Char field for widget display to avoid Many2one template conflicts
    customer_already_exist_widget = fields.Char(
        string="Existing Customer Widget",
        compute="_compute_customer_already_exist_widget",
        store=False
    )
    
    @api.depends('customer_already_exist_id')
    def _compute_customer_already_exist_widget(self):
        """Dummy field for widget rendering"""
        for rec in self:
            rec.customer_already_exist_widget = str(rec.customer_already_exist_id.id) if rec.customer_already_exist_id else False

    @api.depends('phone')
    def _compute_customer_already_exist(self):
        for rec in self:
            rec.customer_already_exist_id = False
            if rec.phone:
                existing_customer = self.env['res.partner'].search([
                    ('phone', '=', rec.phone),
                    ('id', '!=', rec.id)
                ], limit=1)
                if existing_customer:
                    rec.customer_already_exist_id = existing_customer
    ###################################################################################
    def copy(self, default=None):
        """
        if not sales manager cannot duplicate customer records, raise error
        """
        self.ensure_one()

        # check group
        if not self.env.user.has_group('sales_team.group_sale_manager'):
            raise UserError(_("You are not allowed to duplicate customer records. Please contact Sales Manager."))
        return super(ResPartner, self).copy(default)

    # @api.onchange('phone')
    # def _onchange_phone_check_existing(self):
    #     """
    #     Check if customer with same phone exists and show warning
    #     with option to redirect to existing customer
    #     """
    #     if self.phone and not self.id:  # Only for new records
    #         existing = self.env['res.partner'].search([
    #             ('phone', '=', self.phone)
    #         ], limit=1)
    #
    #         if existing:
    #             # Store the existing customer ID for the widget button
    #             self.customer_already_exist_id = existing
    #
    #             # Return warning with action
    #             return {
    #                 'warning': {
    #                     'title': _('Customer Already Exists!'),
    #                     'message': _(
    #                         'A customer with phone number "%s" already exists:\n'
    #                         'Name: %s\n'
    #                         'Click the "Open Existing Customer" button to view the existing record.'
    #                     ) % (self.phone, existing.name or 'N/A'),
    #                 }
    #             }

    def action_open_existing_customer(self):
        """
        Open existing customer form without saving current record.
        This bypasses all field validations and discards the current form.
        """
        # This method works with NewId records (unsaved forms)
        # We access the computed field directly from the recordset
        if hasattr(self, 'customer_already_exist_id') and self.customer_already_exist_id:
            customer_id = self.customer_already_exist_id.id
        else:
            # Fallback: search for existing customer by phone if field not computed
            if self.phone:
                existing = self.env['res.partner'].search([
                    ('phone', '=', self.phone),
                    ('id', '!=', self.id if self.id else 0)
                ], limit=1)
                customer_id = existing.id if existing else False
            else:
                customer_id = False
        
        if not customer_id:
            raise UserError(_("No existing customer found."))
        
        # Return action to open existing customer
        # Using 'target': 'current' will replace current form and discard unsaved changes
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'form',
            'target': 'current',
            'res_id': customer_id,
            'context': self.env.context,
        }
