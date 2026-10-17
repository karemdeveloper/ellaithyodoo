from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class EllaithyPosStockBalance(models.Model):
    _name = "ellaithy.pos.stock.balance"
    _description = "Ellaithy POS Stock Balance"
    _order = "warehouse_id, product_id"

    warehouse_id = fields.Many2one("ellaithy.pos.warehouse", required=True, ondelete="cascade", index=True)
    product_id = fields.Many2one("ellaithy.pos.product", required=True, ondelete="cascade", index=True)
    quantity = fields.Float(default=0.0)
    minimum_stock = fields.Float(related="product_id.minimum_stock", readonly=True)
    low_stock = fields.Boolean(compute="_compute_low_stock")

    _sql_constraints = [("stock_balance_unique", "unique(warehouse_id, product_id)", "A stock balance already exists for this product and warehouse.")]

    @api.depends("quantity", "minimum_stock")
    def _compute_low_stock(self):
        for rec in self:
            rec.low_stock = rec.quantity <= rec.minimum_stock


class EllaithyPosStockMove(models.Model):
    _name = "ellaithy.pos.stock.move"
    _description = "Ellaithy POS Stock Movement"
    _order = "date desc, id desc"

    name = fields.Char(default=lambda self: _("New"), readonly=True, copy=False)
    date = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    move_type = fields.Selection([
        ("opening", "Opening Balance"),
        ("adjust_in", "Adjustment In"),
        ("adjust_out", "Adjustment Out"),
        ("sale", "Sale"),
        ("return", "Customer Return"),
        ("cancel_return", "Cancelled Sale Return"),
    ], required=True, default="adjust_in", index=True)
    warehouse_id = fields.Many2one("ellaithy.pos.warehouse", required=True, ondelete="restrict", index=True)
    product_id = fields.Many2one("ellaithy.pos.product", required=True, ondelete="restrict", index=True)
    quantity = fields.Float(required=True, default=1.0)
    direction = fields.Selection([("in", "In"), ("out", "Out")], required=True, default="in")
    signed_quantity = fields.Float(compute="_compute_signed", store=True)
    order_id = fields.Many2one("ellaithy.pos.order", readonly=True, ondelete="set null")
    user_id = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)
    note = fields.Char()
    posted = fields.Boolean(default=False, readonly=True)

    @api.depends("quantity", "direction")
    def _compute_signed(self):
        for rec in self:
            rec.signed_quantity = rec.quantity if rec.direction == "in" else -rec.quantity

    @api.constrains("quantity")
    def _check_qty(self):
        for rec in self:
            if rec.quantity <= 0:
                raise ValidationError(_("Quantity must be greater than zero."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("ellaithy.pos.stock.move") or _("New")
        return super().create(vals_list)

    def action_post(self):
        for move in self:
            if move.posted:
                continue
            if not self.env.user.has_group("ellaithy_pos.group_ellaithy_pos_admin") and not move.order_id:
                raise UserError(_("Only POS Admin can post manual stock movements."))
            balance = self.env["ellaithy.pos.stock.balance"].search([
                ("warehouse_id", "=", move.warehouse_id.id), ("product_id", "=", move.product_id.id)
            ], limit=1)
            if not balance:
                balance = self.env["ellaithy.pos.stock.balance"].create({
                    "warehouse_id": move.warehouse_id.id, "product_id": move.product_id.id, "quantity": 0.0
                })
            new_qty = balance.quantity + move.signed_quantity
            if move.product_id.track_stock and new_qty < 0:
                raise UserError(_("Insufficient stock for %s. Available: %s") % (move.product_id.display_name, balance.quantity))
            balance.quantity = new_qty
            move.posted = True
        return True
