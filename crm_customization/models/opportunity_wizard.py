from odoo import models, fields, api
from datetime import datetime
from datetime import timedelta

import logging
import pytz
import time

_logger = logging.getLogger(__name__)
from odoo.exceptions import ValidationError

class OpportunityWizard(models.TransientModel):
    _name = 'opportunity.wizard'
    _description = 'Opportunity Wizard'

    name = fields.Char(string="Opportunity Name", required=True)
    brand_id = fields.Many2one('res.brand', string="Brand", required=False)
    brand_id2 = fields.Many2many('res.brand', string="Brand(s)", required=False)
    brand_used_id = fields.Many2many(
        'res.brand',
        'opportunity_wizard_used_brand_rel',
        'wizard_id',
        'brand_id',
        string="Used Brand(s)"
    )
    opportunity_type = fields.Selection([
        ('new', 'New'),
        ('trade_in', 'Trade In'),
        ('used', 'Used'),
        ('service', 'Service'),
    ], string='Opportunity Type', tracking=True,default='new')
    sub_brand_id = fields.Many2one('res.sub.brand', string="Sub Brand", required=False)
    sub_brand_id2 = fields.Many2many('res.sub.brand', string="Sub Brand(s)", required=False)
    sub_brand_used_id = fields.Many2many(
        'res.sub.brand',
        'opportunity_wizard_used_sub_brand_rel',
        'wizard_id',
        'sub_brand_id',
        string="Used Sub Brand(s)"
    )
    area_id = fields.Many2one('res.area', string="Area",required=True)
    branch_id = fields.Many2one('res.branch', string="Branch",required=True)
    source_id = fields.Many2one('res.source', string="Source", required=True)
    sla_duration = fields.Float(string="SLA Duration")
    partner_id = fields.Many2one('res.partner', string="Customer")
    marketing_offer = fields.Many2one('marketing.offers', string='Marketing Offer')
    call_type = fields.Many2one('call.type', string='Call Type', required=True)
    model = fields.Char(string="Model")
    kilometers = fields.Char(string="Kilometers")
    service_id = fields.Many2one('res.service', string='Service')
    hotline_transfer = fields.Boolean(string='Hotline-Transfer',default=False)


    @api.model
    def default_get(self, fields_list):
        """Fallback defaults for callers that did not pass ``default_*`` values.

        The customer form button already passes these defaults in its action
        context, so the normal UI path does not need several extra partner
        field fetches.
        """
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id and not res.get('partner_id'):
            partner_data = self.env['res.partner'].browse(active_id).read(
                ['name', 'area_id', 'branch_id', 'crm_source_id'], load=False
            )
            if partner_data:
                data = partner_data[0]
                res.update({
                    'partner_id': active_id,
                    'name': data.get('name') or '',
                    'area_id': data.get('area_id') or False,
                    'branch_id': data.get('branch_id') or False,
                    'source_id': data.get('crm_source_id') or False,
                })
        return res

    @api.onchange('brand_id2')
    def _onchange_brand_id2(self):
        """Clear sub-brands when brands change (New section)"""
        if self.brand_id2:
            # Keep only sub-brands that belong to selected brands
            valid_sub_brands = self.sub_brand_id2.filtered(lambda sb: sb.brand in self.brand_id2)
            self.sub_brand_id2 = valid_sub_brands
        else:
            # If no brands selected, clear all sub-brands
            self.sub_brand_id2 = False

    @api.onchange('brand_used_id')
    def _onchange_brand_used_id(self):
        """Clear sub-brands when brands change (Used section)"""
        if self.brand_used_id:
            # Keep only sub-brands that belong to selected brands
            valid_sub_brands = self.sub_brand_used_id.filtered(lambda sb: sb.brand in self.brand_used_id)
            self.sub_brand_used_id = valid_sub_brands
        else:
            # If no brands selected, clear all sub-brands
            self.sub_brand_used_id = False

    #################################################################################

    def _get_next_salesperson(self):
        """Return the next salesperson using the shared optimized distributor.

        Keeping the round-robin implementation in ``distribute.sequence``
        avoids duplicated searches and, importantly, avoids the expensive
        ir.config_parameter cache clear that the old wizard implementation did
        on every opportunity creation.
        """
        self.ensure_one()
        if not self.branch_id:
            return False
        return self.env['distribute.sequence']._get_next_salesperson_for_branch(
            self.branch_id.id
        )

    def action_distribute(self):
        """Create the CRM opportunity with the minimum number of DB round trips."""
        started = time.perf_counter()
        self.ensure_one()

        partner = self.partner_id
        has_full_access = self.env.user.has_group(
            'crm_customization.group_access_create_opportunity'
        )

        # Check only for an actually open opportunity and stop at the first hit.
        # The previous implementation loaded every opportunity for the customer,
        # then filtered Python-side, and crm.lead.create() repeated the query.
        if not has_full_access:
            open_opportunity = self.env['crm.lead'].search([
                ('partner_id', '=', partner.id),
                ('type', '=', 'opportunity'),
                ('probability', '<', 100),
                ('active', '=', True),
            ], limit=1)
            if open_opportunity:
                raise ValidationError(
                    "Cannot add opportunity. Customer already has an open opportunity."
                )

        # Reuse the customer's active salesperson; distribute only when needed.
        salesperson = partner.user_id if partner.user_id and partner.user_id.active else False
        if not salesperson:
            salesperson = self._get_next_salesperson()
            if salesperson:
                # Avoid a useless write/tracking cycle if another concurrent path
                # already assigned the same salesperson.
                if partner.user_id.id != salesperson.id:
                    partner.write({'user_id': salesperson.id})

        lead_vals = {
            'sla_duration': '00:00:00',
            'marketing_offer': self.marketing_offer.id,
            'call_type': self.call_type.id,
            'partner_id': partner.id,
            'branch_name': self.branch_id.id if self.branch_id else False,
            'area_name': self.area_id.id if self.area_id else False,
            'source_name': self.source_id.id,
            'user_id': salesperson.id if salesperson else False,
            'type': 'opportunity',
            'brand_name2': [(6, 0, self.brand_id2.ids)],
            'sub_brand_name2': [(6, 0, self.sub_brand_id2.ids)],
            'brand_used_id': [(6, 0, self.brand_used_id.ids)],
            'sub_brand_used_id': [(6, 0, self.sub_brand_used_id.ids)],
            'model': self.model,
            'opportunity_type': self.opportunity_type,
            'kilometers': self.kilometers,
            'service_id': self.service_id.id if self.service_id else False,
            'hotline_transfer': self.hotline_transfer,
        }

        # We already performed the open-opportunity validation above.  Tell the
        # crm.lead override not to run the exact same query a second time.
        lead = self.env['crm.lead'].with_context(
            skip_open_opportunity_check=True
        ).create(lead_vals)

        _logger.info(
            "Opportunity %s created from customer %s in %.3f seconds",
            lead.id, partner.id, time.perf_counter() - started,
        )

        return {
            'type': 'ir.actions.act_window',
            'name': 'Opportunity',
            'view_mode': 'form',
            'res_model': 'crm.lead',
            'res_id': lead.id,
            'target': 'current',
        }

