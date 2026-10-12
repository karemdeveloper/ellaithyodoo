from odoo import models
from odoo.exceptions import ValidationError
import re


def normalize_egypt_phone_local(phone):
    if not phone:
        return False
    phone = re.sub(r"\D", "", phone)

    if phone.startswith("20") and len(phone) == 12:
        return "0" + phone[2:]

    if phone.startswith("201") and len(phone) == 12:
        return "0" + phone[2:]

    if phone.startswith("01") and len(phone) == 11:
        return phone

    return False


class LeadMixin(models.AbstractModel):
    _name = "lead.mixin"
    _description = "Shared Lead Creation Logic"

    def create_lead_request(self, record):
        """Create CRM lead from API or model data using opportunity wizard logic"""

        normalized_phone = normalize_egypt_phone_local(record.phone_number)
        if not normalized_phone:
            raise ValidationError("Invalid phone number")

        # Partner - create or find
        Partner = self.env["res.partner"]
        partner = Partner.search([("phone", "=", normalized_phone)], limit=1)
        if not partner:
            partner = Partner.create(
                {
                    "name": f"{record.first_name} {record.last_name}",
                    "phone": normalized_phone,
                    "email": record.email,
                    "customer_rank": 1,
                }
            )

        # Area - search both English and Arabic
        Area = self.env["res.area"]
        area = Area.search(
            ["|", ("area_name", "ilike", record.area), ("name_ar", "ilike", record.area)],
            limit=1
        )
        if not area:
            raise ValidationError(f"Area '{record.area}' not found")

        # Brand - search both English and Arabic
        Brand = self.env["res.brand"]
        brand = Brand.search(
            ["|", ("brand_name", "ilike", record.car_brand), ("name_ar", "ilike", record.car_brand)],
            limit=1
        )
        if not brand:
            raise ValidationError(f"Car brand '{record.car_brand}' not found")

        # Sub Brand - search both English and Arabic
        SubBrand = self.env["res.sub.brand"]
        sub_brand = SubBrand.search(
            ["|", ("sub_brand_name", "ilike", record.car_model), ("name_ar", "ilike", record.car_model)],
            limit=1
        )
        if not sub_brand:
            raise ValidationError(f"Car model '{record.car_model}' not found")

        # Source (Website)
        Source = self.env["res.source"]
        source = Source.search([("is_website_source", "=", True)], limit=1)
        if not source:
            raise ValidationError("Website source is not configured")

        # Call Type (Website)
        CallType = self.env["call.type"]
        call_type = CallType.search([("is_website_call_type", "=", True)], limit=1)
        if not call_type:
            raise ValidationError("Website call type is not configured")

        # Update partner with area, branch, and source if needed
        partner_vals = {}
        if not partner.area_id:
            partner_vals['area_id'] = area.id
        if not partner.crm_source_id:
            partner_vals['crm_source_id'] = source.id
        # Get branch from area if exists
        if area.branch_area and not partner.branch_id:
            partner_vals['branch_id'] = area.branch_area.id
        if partner_vals:
            partner.write(partner_vals)

        # Create wizard to leverage existing salesperson assignment logic
        wizard = self.env['opportunity.wizard'].create({
            'partner_id': partner.id,
            'name': partner.name,
            'area_id': area.id,
            'branch_id': partner.branch_id.id if partner.branch_id else False,
            'source_id': source.id,
            'brand_id2': [(6, 0, [brand.id])],
            'sub_brand_id2': [(6, 0, [sub_brand.id])],
            'call_type': call_type.id,
            'opportunity_type': 'new',
        })

        # Call the distribution action to create lead with proper salesperson
        result = wizard.action_distribute()

        # Get the created lead and link it to the request
        lead_id = result.get('res_id')
        if lead_id:
            lead = self.env['crm.lead'].browse(lead_id)
            lead.write({'request_id': record.id})
            return lead

        return False

    def create_lead_order(self, record):
        """Create CRM lead from API or model data using opportunity wizard logic"""

        normalized_phone = normalize_egypt_phone_local(record.phone)
        if not normalized_phone:
            raise ValidationError("Invalid phone number")

        # Partner - create or find
        Partner = self.env["res.partner"]
        partner = Partner.search([("phone", "=", normalized_phone)], limit=1)
        if not partner:
            partner = Partner.create(
                {
                    "name": f"{record.first_name} {record.last_name}",
                    "phone": normalized_phone,
                    "email": record.email,
                    "customer_rank": 1,
                }
            )

        # Area - search both English and Arabic
        Area = self.env["res.area"]
        area = Area.search(
            ["|", ("area_name", "ilike", record.area), ("name_ar", "ilike", record.area)],
            limit=1
        )
        if not area:
            raise ValidationError(f"Area '{record.area}' not found")

        # Brand - search both English and Arabic
        Brand = self.env["res.brand"]
        brand = Brand.search(
            ["|", ("brand_name", "ilike", record.car_brand), ("name_ar", "ilike", record.car_brand)],
            limit=1
        )
        if not brand:
            raise ValidationError(f"Car brand '{record.car_brand}' not found")

        # Sub Brand - search both English and Arabic
        SubBrand = self.env["res.sub.brand"]
        sub_brand = SubBrand.search(
            ["|", ("sub_brand_name", "ilike", record.car_model), ("name_ar", "ilike", record.car_model)],
            limit=1
        )
        if not sub_brand:
            raise ValidationError(f"Car model '{record.car_model}' not found")

        # Source (Website)
        Source = self.env["res.source"]
        source = Source.search([("is_website_source", "=", True)], limit=1)
        if not source:
            raise ValidationError("Website source is not configured")

        # Call Type (Website)
        CallType = self.env["call.type"]
        call_type = CallType.search([("is_website_call_type", "=", True)], limit=1)
        if not call_type:
            raise ValidationError("Website call type is not configured")

        # Update partner with area, branch, and source if needed
        partner_vals = {}
        if not partner.area_id:
            partner_vals['area_id'] = area.id
        if not partner.crm_source_id:
            partner_vals['crm_source_id'] = source.id
        # Get branch from area if exists
        if area.branch_area and not partner.branch_id:
            partner_vals['branch_id'] = area.branch_area.id
        if partner_vals:
            partner.write(partner_vals)

        # Create wizard to leverage existing salesperson assignment logic
        wizard = self.env['opportunity.wizard'].create({
            'partner_id': partner.id,
            'name': partner.name,
            'area_id': area.id,
            'branch_id': partner.branch_id.id if partner.branch_id else False,
            'source_id': source.id,
            'brand_id2': [(6, 0, [brand.id])],
            'sub_brand_id2': [(6, 0, [sub_brand.id])],
            'call_type': call_type.id,
            'opportunity_type': 'new',
        })

        # Call the distribution action to create lead with proper salesperson
        result = wizard.action_distribute()

        # Get the created lead and link it to the order
        lead_id = result.get('res_id')
        if lead_id:
            lead = self.env['crm.lead'].browse(lead_id)
            lead.write({'order_id': record.id})
            return lead

        return False
