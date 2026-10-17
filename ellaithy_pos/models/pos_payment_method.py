from odoo import fields, models


class EllaithyPosPaymentMethod(models.Model):
    _name = "ellaithy.pos.payment.method"
    _description = "Ellaithy POS Payment Method"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    requires_reference = fields.Boolean(
        string="Requires Reference",
        help="Require a transaction/reference number when this method is selected.",
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Accounting Journal",
        domain="[('type', 'in', ('bank', 'cash'))]",
        help="Optional journal used by finance when registering payment.",
    )
    note = fields.Text()

    _sql_constraints = [
        ("code_unique", "unique(code)", "Payment method code must be unique."),
    ]
