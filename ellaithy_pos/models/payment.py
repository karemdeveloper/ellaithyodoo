from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class EllaithyPosPayment(models.Model):
    _name = "ellaithy.pos.payment"
    _description = "Ellaithy POS Payment"
    _order = "payment_date desc, id desc"

    name = fields.Char(default=lambda self: _("New"), readonly=True, copy=False)
    order_id = fields.Many2one("ellaithy.pos.order", required=True, ondelete="cascade", index=True)
    payment_date = fields.Datetime(default=fields.Datetime.now, required=True)
    payment_method_id = fields.Many2one("ellaithy.pos.payment.method", required=True, ondelete="restrict")
    amount = fields.Float(required=True)
    reference = fields.Char()
    user_id = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)
    state = fields.Selection([("draft", "Draft"), ("posted", "Posted"), ("cancelled", "Cancelled")], default="draft", required=True)
    note = fields.Char()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("ellaithy.pos.payment") or _("New")
        return super().create(vals_list)

    @api.constrains("amount")
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_("Payment amount must be greater than zero."))

    def action_post(self):
        for payment in self:
            if payment.state != "draft":
                continue
            if payment.payment_method_id.requires_reference and not payment.reference:
                raise UserError(_("A payment reference is required for %s.") % payment.payment_method_id.display_name)
            if payment.amount > payment.order_id.balance_due + 0.0001:
                raise UserError(_("Payment cannot be greater than the order balance."))
            payment.state = "posted"
        return True

    def action_cancel(self):
        for payment in self:
            if payment.state == "posted" and not self.env.user.has_group("ellaithy_pos.group_ellaithy_pos_admin"):
                raise UserError(_("Only POS Admin can cancel a posted payment."))
            payment.state = "cancelled"
        return True
