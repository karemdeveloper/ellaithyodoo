from odoo import models, fields, api
from datetime import datetime
from datetime import timedelta

import logging
import pytz

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
    ], string='Opportunity Type', default='new')
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
        """Pre-fill from context first; query the partner only as fallback.

        res.partner.action_open_create_opportunity_wizard passes the normal
        defaults directly, so this usually performs no extra partner reads.
        """
        res = super().default_get(fields_list)

        # New optimized path: defaults were supplied by the customer action.
        if self.env.context.get('default_partner_id'):
            return res

        # Compatibility path for callers that open this wizard using active_id.
        partner_id = self.env.context.get('active_id')
        if partner_id:
            partner = self.env['res.partner'].browse(partner_id).exists()
            if partner:
                res.update({
                    'partner_id': partner.id,
                    'name': partner.name or '',
                    'area_id': partner.area_id.id or False,
                    'branch_id': partner.branch_id.id or False,
                    'source_id': partner.crm_source_id.id or False,
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
        """Return the next salesperson using the shared distributor.

        The previous popup contained a second full copy of the round-robin
        algorithm. Reusing distribute.sequence avoids duplicate CRM team/member
        searches and keeps one source of truth for assignment.
        """
        self.ensure_one()
        if not self.branch_id:
            return False
        return self.env['distribute.sequence']._get_next_salesperson_for_branch(
            self.branch_id.id
        )

    def action_distribute(self):
        """Button action to create a CRM Opportunity and assign next salesperson"""
        self.ensure_one()
        # The one-open-opportunity rule is enforced centrally by
        # crm.lead.create(). Do not repeat the CRM search here: the old popup
        # did the same check twice, which made Save/Create noticeably slower.

        # Reuse the partner's salesperson only while that user is still active;
        # an archived salesperson falls through to the distribution logic.
        if self.partner_id.user_id and self.partner_id.user_id.active:
            # Use the existing salesperson from partner
            salesperson = self.partner_id.user_id
            _logger.info("Partner id=%s already has salesperson id=%s. Reusing existing assignment.", 
                        self.partner_id.id, salesperson.id)
        else:
            # Get next salesperson from distribution logic
            salesperson = self._get_next_salesperson()
            
            # Save this salesperson to the partner for future use
            if salesperson:
                self.partner_id.write({'user_id': salesperson.id})
                _logger.info("Assigned new salesperson id=%s to partner id=%s", 
                            salesperson.id, self.partner_id.id)

        partner_name = self.partner_id.name or 'Unknown'
        # ✅ Use actual field names from res.brand and res.sub.brand
        sub_brand_names = self.sub_brand_id2.mapped('sub_brand_name')
        brand_names = self.brand_id2.mapped('brand_name')

        # Name will be auto-generated by crm_lead_sequence module based on branch/year/month
        lead = self.env['crm.lead'].create({
            'sla_duration': '00:00:00',
            'marketing_offer': self.marketing_offer.id,
            'call_type': self.call_type.id,
            'partner_id': self.partner_id.id,
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
        })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Opportunity',
            'view_mode': 'form',
            'res_model': 'crm.lead',
            'res_id': lead.id,
            'target': 'current',
        }

        # if self.partner_id:
        #     self.partner_id.is_opportunity = True
        #
        # return {
        #     'type': 'ir.actions.act_window',
        #     'name': 'Opportunity',
        #     'view_mode': 'form',
        #     'res_model': 'crm.lead',
        #     'res_id': lead.id,
        #     'target': 'current',
        # }
