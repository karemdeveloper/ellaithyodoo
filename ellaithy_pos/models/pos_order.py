from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class EllaithyPosOrder(models.Model):
    _name = "ellaithy.pos.order"
    _description = "Ellaithy POS Order Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
        tracking=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("requested", "Requested"),
            ("approved", "Approved"),
            ("confirmed", "ERP Confirmed"),
            ("invoiced", "Invoiced"),
            ("done", "Done"),
            ("rejected", "Rejected"),
            ("cancel", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    request_date = fields.Datetime(default=fields.Datetime.now, required=True, tracking=True)
    user_id = fields.Many2one(
        "res.users",
        string="Requested By",
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
    )
    salesperson_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        default=lambda self: self.env.user,
        tracking=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        tracking=True,
        domain="[('customer_rank', '>', 0)]",
    )
    customer_phone = fields.Char(related="partner_id.phone", store=False, readonly=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Warehouse",
        required=True,
        default=lambda self: self._default_warehouse(),
        domain="[('company_id', '=', company_id)]",
        tracking=True,
    )
    payment_method_id = fields.Many2one(
        "ellaithy.pos.payment.method",
        string="Payment Method",
        tracking=True,
    )
    payment_reference = fields.Char(string="Payment Reference", tracking=True)
    notes = fields.Text()
    rejection_reason = fields.Text(tracking=True)

    line_ids = fields.One2many(
        "ellaithy.pos.order.line",
        "order_id",
        string="Order Lines",
        copy=True,
    )

    amount_untaxed = fields.Monetary(compute="_compute_amounts", store=True)
    amount_tax = fields.Monetary(compute="_compute_amounts", store=True)
    amount_total = fields.Monetary(compute="_compute_amounts", store=True)
    total_cost = fields.Monetary(compute="_compute_amounts", store=True)
    margin = fields.Monetary(compute="_compute_amounts", store=True)
    margin_percent = fields.Float(compute="_compute_amounts", store=True)

    sale_order_id = fields.Many2one("sale.order", string="Sales Order", copy=False, readonly=True, tracking=True)
    invoice_count = fields.Integer(compute="_compute_erp_counts")
    picking_count = fields.Integer(compute="_compute_erp_counts")
    invoice_status = fields.Selection(related="sale_order_id.invoice_status", readonly=True)
    is_pos_manager = fields.Boolean(compute="_compute_is_pos_manager")

    def _compute_is_pos_manager(self):
        is_manager = self.env.user.has_group("ellaithy_pos.group_ellaithy_pos_manager")
        for order in self:
            order.is_pos_manager = is_manager

    @api.model
    def _default_warehouse(self):
        return self.env["stock.warehouse"].search([("company_id", "=", self.env.company.id)], limit=1)

    @api.depends(
        "line_ids.price_subtotal",
        "line_ids.price_tax",
        "line_ids.price_total",
        "line_ids.cost_total",
    )
    def _compute_amounts(self):
        for order in self:
            untaxed = sum(order.line_ids.mapped("price_subtotal"))
            tax = sum(order.line_ids.mapped("price_tax"))
            total = sum(order.line_ids.mapped("price_total"))
            cost = sum(order.line_ids.mapped("cost_total"))
            order.amount_untaxed = untaxed
            order.amount_tax = tax
            order.amount_total = total
            order.total_cost = cost
            order.margin = untaxed - cost
            order.margin_percent = (order.margin / untaxed * 100.0) if untaxed else 0.0

    def _compute_erp_counts(self):
        for order in self:
            if order.sale_order_id:
                order.invoice_count = len(order.sale_order_id.invoice_ids)
                order.picking_count = len(order.sale_order_id.picking_ids)
            else:
                order.invoice_count = 0
                order.picking_count = 0

    @api.constrains("payment_method_id", "payment_reference")
    def _check_payment_reference(self):
        for order in self:
            if order.payment_method_id.requires_reference and not order.payment_reference:
                raise ValidationError(_("Payment reference is required for the selected payment method."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("ellaithy.pos.order") or _("New")
        return super().create(vals_list)

    def write(self, vals):
        if "line_ids" in vals:
            blocked = self.filtered(lambda r: r.state not in ("draft", "rejected"))
            if blocked and not self.env.user.has_group("ellaithy_pos.group_ellaithy_pos_manager"):
                raise UserError(_("Only a POS Manager can change lines after the request is submitted."))
        return super().write(vals)

    def action_submit(self):
        for order in self:
            if not order.line_ids:
                raise UserError(_("Add at least one product before submitting the order."))
            if order.amount_total <= 0:
                raise UserError(_("Order total must be greater than zero."))
            order.state = "requested"
        return True

    def action_approve(self):
        self._require_manager()
        for order in self:
            if order.state != "requested":
                raise UserError(_("Only requested orders can be approved."))
            order.state = "approved"
            order.message_post(body=_("Order request approved by %s") % self.env.user.display_name)
        return True

    def action_reject(self):
        self._require_manager()
        for order in self:
            if not order.rejection_reason:
                raise UserError(_("Enter a rejection reason before rejecting the request."))
            order.state = "rejected"
            order.message_post(body=_("Order request rejected by %s") % self.env.user.display_name)
        return True

    def action_reset_to_draft(self):
        for order in self:
            if order.state not in ("rejected", "cancel"):
                raise UserError(_("Only rejected or cancelled requests can be reset to draft."))
            if order.sale_order_id:
                raise UserError(_("This request already has an ERP Sales Order and cannot be reset."))
            order.state = "draft"
        return True

    def action_cancel(self):
        for order in self:
            if order.sale_order_id and order.sale_order_id.state not in ("draft", "cancel"):
                raise UserError(_("Cancel the related Sales Order first."))
            if order.sale_order_id and order.sale_order_id.state == "draft":
                order.sale_order_id.action_cancel()
            order.state = "cancel"
        return True

    def _require_manager(self):
        if not self.env.user.has_group("ellaithy_pos.group_ellaithy_pos_manager"):
            raise UserError(_("Only a POS Manager can perform this action."))

    def _prepare_sale_order_vals(self):
        self.ensure_one()
        return {
            "partner_id": self.partner_id.id,
            "user_id": self.salesperson_id.id,
            "warehouse_id": self.warehouse_id.id,
            "company_id": self.company_id.id,
            "client_order_ref": self.name,
            "origin": self.name,
            "note": self.notes or False,
            "order_line": [
                (0, 0, {
                    "product_id": line.product_id.id,
                    "name": line.name,
                    "product_uom_qty": line.quantity,
                    "product_uom": line.uom_id.id,
                    "price_unit": line.price_unit,
                    "discount": line.discount,
                    "tax_id": [(6, 0, line.tax_ids.ids)],
                })
                for line in self.line_ids
            ],
        }

    def action_confirm_erp(self):
        self._require_manager()
        SaleOrder = self.env["sale.order"]
        for order in self:
            if order.state != "approved":
                raise UserError(_("Approve the order before confirming it in ERP."))
            if order.sale_order_id:
                raise UserError(_("An ERP Sales Order already exists for this request."))
            sale = SaleOrder.create(order._prepare_sale_order_vals())
            sale.action_confirm()
            order.sale_order_id = sale
            order.state = "confirmed"
            order.message_post(body=_("ERP Sales Order %s created and confirmed.") % sale.name)
        return self.action_open_sale_order()

    def action_create_invoice(self):
        self._require_manager()
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError(_("Create the ERP Sales Order first."))
        if self.sale_order_id.state not in ("sale", "done"):
            raise UserError(_("The Sales Order must be confirmed before invoicing."))
        invoices = self.sale_order_id._create_invoices()
        if not invoices:
            raise UserError(_("No invoiceable lines were found."))
        self.state = "invoiced"
        if len(invoices) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("Customer Invoice"),
                "res_model": "account.move",
                "view_mode": "form",
                "res_id": invoices.id,
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Customer Invoices"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", invoices.ids)],
        }

    def action_mark_done(self):
        self._require_manager()
        for order in self:
            if not order.sale_order_id:
                raise UserError(_("There is no ERP Sales Order for this request."))
            open_pickings = order.sale_order_id.picking_ids.filtered(lambda p: p.state not in ("done", "cancel"))
            unpaid = order.sale_order_id.invoice_ids.filtered(
                lambda m: m.state == "posted" and m.payment_state not in ("paid", "reversed")
            )
            if open_pickings:
                raise UserError(_("Complete or cancel all deliveries before marking the POS order as done."))
            if unpaid:
                raise UserError(_("All posted invoices must be paid before marking the POS order as done."))
            order.state = "done"
        return True

    def action_open_sale_order(self):
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError(_("No Sales Order has been created yet."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Sales Order"),
            "res_model": "sale.order",
            "view_mode": "form",
            "res_id": self.sale_order_id.id,
        }

    def action_open_invoices(self):
        self.ensure_one()
        invoices = self.sale_order_id.invoice_ids if self.sale_order_id else self.env["account.move"]
        if not invoices:
            raise UserError(_("No invoices have been created yet."))
        if len(invoices) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("Customer Invoice"),
                "res_model": "account.move",
                "view_mode": "form",
                "res_id": invoices.id,
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Customer Invoices"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", invoices.ids)],
        }

    def action_open_pickings(self):
        self.ensure_one()
        pickings = self.sale_order_id.picking_ids if self.sale_order_id else self.env["stock.picking"]
        if not pickings:
            raise UserError(_("No deliveries have been created yet."))
        if len(pickings) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("Delivery"),
                "res_model": "stock.picking",
                "view_mode": "form",
                "res_id": pickings.id,
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Deliveries"),
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": [("id", "in", pickings.ids)],
        }


class EllaithyPosOrderLine(models.Model):
    _name = "ellaithy.pos.order.line"
    _description = "Ellaithy POS Order Line"
    _order = "id"

    order_id = fields.Many2one("ellaithy.pos.order", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="order_id.company_id", store=True, readonly=True)
    currency_id = fields.Many2one(related="order_id.currency_id", readonly=True)
    product_id = fields.Many2one(
        "product.product",
        required=True,
        domain="[('sale_ok', '=', True)]",
    )
    name = fields.Char(required=True)
    quantity = fields.Float(default=1.0, required=True)
    uom_id = fields.Many2one("uom.uom", string="UoM", required=True)
    price_unit = fields.Monetary(required=True)
    discount = fields.Float(default=0.0)
    tax_ids = fields.Many2many("account.tax", string="Taxes")
    price_subtotal = fields.Monetary(compute="_compute_amount", store=True)
    price_tax = fields.Monetary(compute="_compute_amount", store=True)
    price_total = fields.Monetary(compute="_compute_amount", store=True)
    standard_price = fields.Float(related="product_id.standard_price", readonly=True)
    cost_total = fields.Monetary(compute="_compute_amount", store=True)
    available_qty = fields.Float(compute="_compute_available_qty")

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if not self.product_id:
            return
        self.name = self.product_id.get_product_multiline_description_sale() or self.product_id.display_name
        self.uom_id = self.product_id.uom_id
        self.price_unit = self.product_id.lst_price
        self.tax_ids = self.product_id.taxes_id.filtered(lambda t: t.company_id == self.order_id.company_id)

    @api.depends("product_id", "order_id.warehouse_id")
    def _compute_available_qty(self):
        for line in self:
            if not line.product_id or not line.order_id.warehouse_id:
                line.available_qty = 0.0
                continue
            product = line.product_id.with_context(warehouse=line.order_id.warehouse_id.id)
            line.available_qty = product.qty_available

    @api.depends("quantity", "price_unit", "discount", "tax_ids", "standard_price")
    def _compute_amount(self):
        for line in self:
            discounted_price = line.price_unit * (1.0 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_ids.compute_all(
                discounted_price,
                currency=line.currency_id,
                quantity=line.quantity,
                product=line.product_id,
                partner=line.order_id.partner_id,
            )
            line.price_subtotal = taxes["total_excluded"]
            line.price_tax = taxes["total_included"] - taxes["total_excluded"]
            line.price_total = taxes["total_included"]
            line.cost_total = line.standard_price * line.quantity

    @api.constrains("quantity", "discount")
    def _check_values(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(_("Quantity must be greater than zero."))
            if line.discount < 0 or line.discount > 100:
                raise ValidationError(_("Discount must be between 0 and 100 percent."))
