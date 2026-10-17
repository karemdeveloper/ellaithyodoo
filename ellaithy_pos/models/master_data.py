from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class EllaithyPosCategory(models.Model):
    _name = "ellaithy.pos.category"
    _description = "Ellaithy POS Product Category"
    _order = "name"

    name = fields.Char(required=True, index=True)
    parent_id = fields.Many2one("ellaithy.pos.category", string="Parent Category", ondelete="restrict")
    active = fields.Boolean(default=True)
    note = fields.Text()


class EllaithyPosWarehouse(models.Model):
    _name = "ellaithy.pos.warehouse"
    _description = "Ellaithy POS Warehouse"
    _order = "name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)
    location = fields.Char()
    responsible_id = fields.Many2one("res.users", string="Responsible User")
    note = fields.Text()

    _sql_constraints = [("warehouse_code_unique", "unique(code)", "Warehouse code must be unique.")]


class EllaithyPosCustomer(models.Model):
    _name = "ellaithy.pos.customer"
    _description = "Ellaithy POS Customer"
    _order = "name"

    name = fields.Char(required=True, index=True)
    phone = fields.Char(index=True)
    mobile = fields.Char()
    email = fields.Char()
    tax_number = fields.Char(string="Tax Number")
    address = fields.Text()
    active = fields.Boolean(default=True)
    note = fields.Text()


class EllaithyPosProduct(models.Model):
    _name = "ellaithy.pos.product"
    _description = "Ellaithy POS Product"
    _order = "name"

    name = fields.Char(required=True, index=True)
    sku = fields.Char(string="SKU", required=True, index=True)
    barcode = fields.Char(index=True)
    category_id = fields.Many2one("ellaithy.pos.category", required=True, ondelete="restrict")
    uom = fields.Selection([
        ("unit", "Unit"), ("pack", "Pack"), ("box", "Box"), ("ream", "Ream"),
        ("bottle", "Bottle"), ("kg", "Kilogram"), ("liter", "Liter"), ("set", "Set")
    ], default="unit", required=True)
    cost_price = fields.Float(required=True, default=0.0, digits=(16, 4))
    sale_price = fields.Float(required=True, default=0.0, digits=(16, 4))
    tax_percent = fields.Float(string="Tax %", default=0.0)
    track_stock = fields.Boolean(default=True)
    minimum_stock = fields.Float(default=0.0)
    active = fields.Boolean(default=True)
    note = fields.Text()
    stock_balance_ids = fields.One2many("ellaithy.pos.stock.balance", "product_id", string="Stock")
    total_on_hand = fields.Float(compute="_compute_total_on_hand")

    _sql_constraints = [("product_sku_unique", "unique(sku)", "SKU must be unique.")]

    @api.depends("stock_balance_ids.quantity")
    def _compute_total_on_hand(self):
        for rec in self:
            rec.total_on_hand = sum(rec.stock_balance_ids.mapped("quantity"))

    @api.constrains("tax_percent")
    def _check_tax(self):
        for rec in self:
            if rec.tax_percent < 0 or rec.tax_percent > 100:
                raise ValidationError(_("Tax percentage must be between 0 and 100."))


class EllaithyPosPaymentMethod(models.Model):
    _name = "ellaithy.pos.payment.method"
    _description = "Ellaithy POS Payment Method"
    _order = "sequence, name"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    requires_reference = fields.Boolean()
    allow_partial = fields.Boolean(default=True)
    note = fields.Text()
