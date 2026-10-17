from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class EllaithyPosOrder(models.Model):
    _name = "ellaithy.pos.order"
    _description = "Ellaithy POS Order"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(default=lambda self: _("New"), required=True, readonly=True, copy=False, tracking=True)
    order_type = fields.Selection([("sale", "Sale"), ("return", "Return")], default="sale", required=True, tracking=True)
    original_order_id = fields.Many2one("ellaithy.pos.order", string="Original Sale", domain="[('order_type','=','sale'),('state','=','done')]", tracking=True)
    state = fields.Selection([
        ("draft", "Draft"), ("requested", "Requested"), ("approved", "Approved"),
        ("processing", "Processing"), ("done", "Done"), ("rejected", "Rejected"), ("cancel", "Cancelled")
    ], default="draft", required=True, tracking=True, index=True)
    request_date = fields.Datetime(default=fields.Datetime.now, required=True, tracking=True, index=True)
    completed_date = fields.Datetime(readonly=True, tracking=True)
    requester_id = fields.Many2one("res.users", default=lambda self: self.env.user, required=True, readonly=True, tracking=True)
    operator_id = fields.Many2one("res.users", string="POS Operator", readonly=True, tracking=True)
    customer_id = fields.Many2one("ellaithy.pos.customer", required=True, ondelete="restrict", tracking=True)
    warehouse_id = fields.Many2one("ellaithy.pos.warehouse", required=True, ondelete="restrict", tracking=True)
    payment_method_id = fields.Many2one("ellaithy.pos.payment.method", tracking=True)
    payment_reference = fields.Char(tracking=True)
    notes = fields.Text()
    rejection_reason = fields.Text(tracking=True)

    line_ids = fields.One2many("ellaithy.pos.order.line", "order_id", copy=True)
    payment_ids = fields.One2many("ellaithy.pos.payment", "order_id")
    stock_move_ids = fields.One2many("ellaithy.pos.stock.move", "order_id")

    amount_before_discount = fields.Float(compute="_compute_amounts", store=True)
    amount_discount = fields.Float(compute="_compute_amounts", store=True)
    amount_untaxed = fields.Float(compute="_compute_amounts", store=True)
    amount_tax = fields.Float(compute="_compute_amounts", store=True)
    amount_total = fields.Float(compute="_compute_amounts", store=True)
    total_cost = fields.Float(compute="_compute_amounts", store=True)
    margin = fields.Float(compute="_compute_amounts", store=True)
    margin_percent = fields.Float(compute="_compute_amounts", store=True)
    amount_paid = fields.Float(compute="_compute_payment", store=True)
    balance_due = fields.Float(compute="_compute_payment", store=True)
    payment_status = fields.Selection([("unpaid", "Unpaid"), ("partial", "Partially Paid"), ("paid", "Paid")], compute="_compute_payment", store=True)
    line_count = fields.Integer(compute="_compute_counts")
    payment_count = fields.Integer(compute="_compute_counts")

    is_operator = fields.Boolean(compute="_compute_roles")
    is_admin = fields.Boolean(compute="_compute_roles")

    def _compute_roles(self):
        op = self.env.user.has_group("ellaithy_pos.group_ellaithy_pos_operator")
        admin = self.env.user.has_group("ellaithy_pos.group_ellaithy_pos_admin")
        for rec in self:
            rec.is_operator = op or admin
            rec.is_admin = admin

    @api.depends("line_ids.price_before_discount", "line_ids.discount_amount", "line_ids.price_subtotal", "line_ids.price_tax", "line_ids.price_total", "line_ids.cost_total")
    def _compute_amounts(self):
        for order in self:
            order.amount_before_discount = sum(order.line_ids.mapped("price_before_discount"))
            order.amount_discount = sum(order.line_ids.mapped("discount_amount"))
            order.amount_untaxed = sum(order.line_ids.mapped("price_subtotal"))
            order.amount_tax = sum(order.line_ids.mapped("price_tax"))
            order.amount_total = sum(order.line_ids.mapped("price_total"))
            order.total_cost = sum(order.line_ids.mapped("cost_total"))
            order.margin = order.amount_untaxed - order.total_cost
            order.margin_percent = (order.margin / order.amount_untaxed * 100.0) if order.amount_untaxed else 0.0

    @api.depends("payment_ids.amount", "payment_ids.state", "amount_total")
    def _compute_payment(self):
        for order in self:
            paid = sum(p.amount for p in order.payment_ids if p.state == "posted")
            order.amount_paid = paid
            order.balance_due = max(order.amount_total - paid, 0.0)
            if paid <= 0:
                order.payment_status = "unpaid"
            elif order.balance_due > 0.0001:
                order.payment_status = "partial"
            else:
                order.payment_status = "paid"

    @api.depends("line_ids", "payment_ids")
    def _compute_counts(self):
        for order in self:
            order.line_count = len(order.line_ids)
            order.payment_count = len(order.payment_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("ellaithy.pos.order") or _("New")
        return super().create(vals_list)

    def write(self, vals):
        protected = {"line_ids", "customer_id", "warehouse_id", "order_type", "original_order_id"}
        if protected.intersection(vals):
            blocked = self.filtered(lambda o: o.state not in ("draft", "rejected"))
            if blocked and not self.env.user.has_group("ellaithy_pos.group_ellaithy_pos_admin"):
                raise UserError(_("Only POS Admin can modify order contents after submission."))
        return super().write(vals)

    def action_submit(self):
        for order in self:
            if not order.line_ids:
                raise UserError(_("Add at least one product."))
            if order.amount_total <= 0:
                raise UserError(_("Order total must be greater than zero."))
            order.state = "requested"
        return True

    def _require_operator(self):
        if not (self.env.user.has_group("ellaithy_pos.group_ellaithy_pos_operator") or self.env.user.has_group("ellaithy_pos.group_ellaithy_pos_admin")):
            raise UserError(_("Only POS Operator or POS Admin can perform this action."))

    def action_approve(self):
        self._require_operator()
        for order in self:
            if order.state != "requested":
                raise UserError(_("Only requested orders can be approved."))
            order.write({"state": "approved", "operator_id": self.env.user.id})
        return True

    def action_start_processing(self):
        self._require_operator()
        for order in self:
            if order.state != "approved":
                raise UserError(_("Approve the order first."))
            order.write({"state": "processing", "operator_id": self.env.user.id})
        return True

    def action_reject(self):
        self._require_operator()
        for order in self:
            if not order.rejection_reason:
                raise UserError(_("Enter a rejection reason first."))
            order.state = "rejected"
        return True

    def action_done(self):
        self._require_operator()
        Move = self.env["ellaithy.pos.stock.move"]
        for order in self:
            if order.state not in ("approved", "processing"):
                raise UserError(_("Only approved/processing orders can be completed."))
            if order.order_type == "sale" and order.balance_due > 0.0001:
                raise UserError(_("The order must be fully paid before completion."))
            if order.stock_move_ids.filtered(lambda m: m.posted):
                raise UserError(_("Stock was already posted for this order."))
            for line in order.line_ids:
                if not line.product_id.track_stock:
                    continue
                move = Move.create({
                    "move_type": "sale" if order.order_type == "sale" else "return",
                    "warehouse_id": order.warehouse_id.id,
                    "product_id": line.product_id.id,
                    "quantity": line.quantity,
                    "direction": "out" if order.order_type == "sale" else "in",
                    "order_id": order.id,
                    "note": order.name,
                })
                move.action_post()
            order.write({"state": "done", "completed_date": fields.Datetime.now(), "operator_id": self.env.user.id})
        return True

    def action_cancel(self):
        for order in self:
            if order.state == "done":
                raise UserError(_("Completed orders cannot be cancelled. Create a return order instead."))
            order.state = "cancel"
        return True

    def action_reset_draft(self):
        for order in self:
            if order.state not in ("rejected", "cancel"):
                raise UserError(_("Only rejected/cancelled orders can be reset."))
            order.state = "draft"
        return True


class EllaithyPosOrderLine(models.Model):
    _name = "ellaithy.pos.order.line"
    _description = "Ellaithy POS Order Line"
    _order = "id"

    order_id = fields.Many2one("ellaithy.pos.order", required=True, ondelete="cascade", index=True)
    product_id = fields.Many2one("ellaithy.pos.product", required=True, ondelete="restrict", index=True)
    category_id = fields.Many2one(related="product_id.category_id", store=True, readonly=True)
    sku = fields.Char(related="product_id.sku", readonly=True)
    quantity = fields.Float(default=1.0, required=True)
    unit_price = fields.Float(required=True)
    discount_percent = fields.Float(string="Discount %", default=0.0)
    tax_percent = fields.Float(string="Tax %", default=0.0)
    unit_cost = fields.Float(readonly=True)
    available_qty = fields.Float(compute="_compute_available")
    price_before_discount = fields.Float(compute="_compute_values", store=True)
    discount_amount = fields.Float(compute="_compute_values", store=True)
    price_subtotal = fields.Float(compute="_compute_values", store=True)
    price_tax = fields.Float(compute="_compute_values", store=True)
    price_total = fields.Float(compute="_compute_values", store=True)
    cost_total = fields.Float(compute="_compute_values", store=True)
    margin = fields.Float(compute="_compute_values", store=True)

    @api.onchange("product_id")
    def _onchange_product(self):
        if self.product_id:
            self.unit_price = self.product_id.sale_price
            self.unit_cost = self.product_id.cost_price
            self.tax_percent = self.product_id.tax_percent

    @api.depends("product_id", "order_id.warehouse_id")
    def _compute_available(self):
        Balance = self.env["ellaithy.pos.stock.balance"]
        for line in self:
            if line.product_id and line.order_id.warehouse_id:
                bal = Balance.search([("warehouse_id", "=", line.order_id.warehouse_id.id), ("product_id", "=", line.product_id.id)], limit=1)
                line.available_qty = bal.quantity if bal else 0.0
            else:
                line.available_qty = 0.0

    @api.depends("quantity", "unit_price", "discount_percent", "tax_percent", "unit_cost")
    def _compute_values(self):
        for line in self:
            gross = line.quantity * line.unit_price
            discount = gross * line.discount_percent / 100.0
            subtotal = gross - discount
            tax = subtotal * line.tax_percent / 100.0
            line.price_before_discount = gross
            line.discount_amount = discount
            line.price_subtotal = subtotal
            line.price_tax = tax
            line.price_total = subtotal + tax
            line.cost_total = line.quantity * line.unit_cost
            line.margin = subtotal - line.cost_total

    @api.constrains("quantity", "discount_percent", "tax_percent")
    def _check_values(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(_("Quantity must be greater than zero."))
            if not 0 <= line.discount_percent <= 100:
                raise ValidationError(_("Discount must be between 0 and 100%."))
            if not 0 <= line.tax_percent <= 100:
                raise ValidationError(_("Tax must be between 0 and 100%."))
