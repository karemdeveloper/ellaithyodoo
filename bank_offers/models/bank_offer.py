from math import pow
import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class BankOfferBank(models.Model):
    _name = "bank.offer.bank"
    _description = "Financing Bank"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(tracking=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)
    sale_ban_fee = fields.Monetary(string="Default Sale-ban Fee", tracking=True)
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id.id,
        required=True,
    )
    website = fields.Char()
    contact_name = fields.Char()
    contact_phone = fields.Char()
    contact_email = fields.Char()
    last_verified_date = fields.Date(string="Last Verified", tracking=True)
    verified_by_id = fields.Many2one("res.users", string="Verified By", tracking=True)
    notes = fields.Text()
    program_ids = fields.One2many("bank.offer.program", "bank_id", string="Programs")
    program_count = fields.Integer(compute="_compute_program_count")

    @api.depends("program_ids")
    def _compute_program_count(self):
        for rec in self:
            rec.program_count = len(rec.program_ids)

    def action_view_programs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Bank Programs"),
            "res_model": "bank.offer.program",
            "view_mode": "list,form",
            "domain": [("bank_id", "=", self.id)],
            "context": {"default_bank_id": self.id},
        }


class BankOfferJobType(models.Model):
    _name = "bank.offer.job.type"
    _description = "Bank Offer Job Type"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("job_type_name_unique", "unique(name)", "Job type name must be unique."),
    ]


class BankOfferProgram(models.Model):
    _name = "bank.offer.program"
    _description = "Bank Financing Program"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "bank_id, sequence, name"

    name = fields.Char(required=True, tracking=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)
    bank_id = fields.Many2one("bank.offer.bank", required=True, ondelete="cascade", tracking=True)
    currency_id = fields.Many2one(related="bank_id.currency_id", store=True, readonly=True)

    vehicle_type = fields.Selection([
        ("any", "Any Vehicle"),
        ("new", "New"),
        ("used", "Used"),
        ("electric", "Electric"),
        ("commercial", "Commercial / Van / Truck"),
    ], default="any", required=True, tracking=True)
    used_vehicle_min_year = fields.Integer(string="Minimum Used Model Year")

    min_downpayment_pct = fields.Float(string="Minimum Down Payment %", default=0.0, tracking=True)
    max_downpayment_pct = fields.Float(string="Maximum Down Payment %", default=100.0)
    min_term_months = fields.Integer(string="Minimum Term (Months)", default=6)
    max_term_months = fields.Integer(string="Maximum Term (Months)", default=84)
    min_customer_age = fields.Integer(string="Minimum Customer Age", default=18)
    max_customer_age = fields.Integer(string="Maximum Customer Age")
    max_age_at_end = fields.Integer(string="Maximum Age at End of Term")
    min_monthly_income = fields.Monetary(string="Minimum Monthly Income")
    max_car_price = fields.Monetary(string="Maximum Vehicle Price")
    min_finance_amount = fields.Monetary(string="Minimum Finance Amount")
    max_finance_amount = fields.Monetary(string="Maximum Finance Amount")
    max_installment_income_pct = fields.Float(
        string="Maximum Installment / Income %",
        help="If set, the calculated monthly installment cannot exceed this percentage of the customer's monthly income.",
    )

    approval_days = fields.Integer(string="Expected Approval Days", default=3, required=True, tracking=True)
    accepted_job_type_ids = fields.Many2many(
        "bank.offer.job.type",
        "bank_offer_program_job_rel",
        "program_id",
        "job_type_id",
        string="Accepted Job Types",
        help="Leave empty to allow all job types.",
    )

    home_inquiry = fields.Selection([
        ("required", "Required"),
        ("optional", "Optional"),
        ("none", "Not Required"),
    ], default="optional")
    work_inquiry = fields.Selection([
        ("required", "Required"),
        ("optional", "Optional"),
        ("none", "Not Required"),
    ], default="optional")
    iscore_required = fields.Boolean(string="I-Score Required")
    negative_area_allowed = fields.Boolean(string="Negative Area Allowed", default=True)

    required_documents = fields.Text()
    acceptance_criteria = fields.Text()
    special_notes = fields.Text()
    effective_from = fields.Date()
    effective_to = fields.Date()
    last_verified_date = fields.Date(string="Last Verified", tracking=True)
    verified_by_id = fields.Many2one("res.users", string="Verified By")

    rate_line_ids = fields.One2many("bank.offer.rate", "program_id", string="Rates")

    def _parsed_import_values(self):
        """Parse the compact imported program name used by the supplied Excel sheet.

        Examples include:
        `... - موظف | 14% | إجباري` and
        `... - صاحب عمل | 12.4% | بدون تأمين`.
        """
        self.ensure_one()
        text = (self.name or "").strip()
        parts = [part.strip() for part in text.split("|")]
        rate = False
        if len(parts) >= 2:
            match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%", parts[1])
            if match:
                rate = float(match.group(1))

        insurance_required = False
        if len(parts) >= 3:
            insurance_text = parts[2]
            # If the source explicitly permits no insurance, do not force it.
            if "بدون تأمين" in insurance_text or "اختياري" in insurance_text:
                insurance_required = False
            elif "إجباري" in insurance_text:
                insurance_required = True

        prefix = parts[0] if parts else text
        job_xmlid = False
        if "فري لانسر" in prefix:
            job_xmlid = "bank_offers.job_freelancer"
        elif "صاحب عمل" in prefix:
            job_xmlid = "bank_offers.job_business_owner"
        elif "موظف" in prefix:
            job_xmlid = "bank_offers.job_employee"
        elif "معاش" in prefix:
            job_xmlid = "bank_offers.job_pension"

        return {
            "annual_interest_rate": rate,
            "insurance_required": insurance_required,
            "job_xmlid": job_xmlid,
        }

    def _ensure_imported_rate(self):
        """Create a usable rate row for imported programs that only carry the rate in Name."""
        self.ensure_one()
        if self.rate_line_ids:
            return self.rate_line_ids
        parsed = self._parsed_import_values()
        if parsed["annual_interest_rate"] is False:
            return self.env["bank.offer.rate"]
        rate = self.env["bank.offer.rate"].create({
            "program_id": self.id,
            "min_downpayment_pct": self.min_downpayment_pct,
            "max_downpayment_pct": self.max_downpayment_pct,
            "min_term_months": self.min_term_months,
            "max_term_months": self.max_term_months,
            "annual_interest_rate": parsed["annual_interest_rate"],
            "interest_method": "flat",
            "insurance_required": parsed["insurance_required"],
            "notes": _("Auto-created from imported program name"),
        })
        if not self.accepted_job_type_ids and parsed["job_xmlid"]:
            job = self.env.ref(parsed["job_xmlid"], raise_if_not_found=False)
            if job:
                self.accepted_job_type_ids = [(6, 0, [job.id])]
        return rate

    @api.model
    def _backfill_imported_rates(self):
        programs = self.search([("active", "=", True), ("bank_id.active", "=", True)])
        for program in programs:
            program._ensure_imported_rate()
        return True

    @api.constrains(
        "min_downpayment_pct", "max_downpayment_pct", "min_term_months", "max_term_months",
        "min_customer_age", "max_customer_age", "max_age_at_end", "approval_days",
        "max_installment_income_pct"
    )
    def _check_ranges(self):
        for rec in self:
            if rec.min_downpayment_pct < 0 or rec.max_downpayment_pct > 100 or rec.min_downpayment_pct > rec.max_downpayment_pct:
                raise ValidationError(_("Down payment percentages are not valid."))
            if rec.min_term_months <= 0 or rec.max_term_months < rec.min_term_months:
                raise ValidationError(_("Financing term range is not valid."))
            if rec.max_customer_age and rec.max_customer_age < rec.min_customer_age:
                raise ValidationError(_("Maximum customer age cannot be less than minimum age."))
            if rec.approval_days < 0:
                raise ValidationError(_("Expected approval days cannot be negative."))
            if rec.max_installment_income_pct < 0 or rec.max_installment_income_pct > 100:
                raise ValidationError(_("Installment / income percentage must be between 0 and 100."))


class BankOfferRate(models.Model):
    _name = "bank.offer.rate"
    _description = "Bank Financing Rate"
    _order = "min_downpayment_pct, min_term_months, annual_interest_rate"

    program_id = fields.Many2one("bank.offer.program", required=True, ondelete="cascade")
    currency_id = fields.Many2one(related="program_id.currency_id", store=True, readonly=True)
    name = fields.Char(compute="_compute_name", store=True)
    active = fields.Boolean(default=True)
    min_downpayment_pct = fields.Float(string="Min Down Payment %", required=True)
    max_downpayment_pct = fields.Float(string="Max Down Payment %", default=100.0, required=True)
    min_term_months = fields.Integer(string="Min Term", default=12, required=True)
    max_term_months = fields.Integer(string="Max Term", default=60, required=True)
    annual_interest_rate = fields.Float(string="Annual Interest %", required=True)
    interest_method = fields.Selection([
        ("flat", "Flat Rate"),
        ("reducing", "Reducing Balance"),
    ], default="flat", required=True)
    insurance_required = fields.Boolean(string="Comprehensive Insurance Required")
    insurance_rate_pct = fields.Float(string="Comprehensive Insurance %")
    admin_fee_pct = fields.Float(string="Administrative Fee %")
    sale_ban_fee = fields.Monetary(
        string="Sale-ban Fee",
        help="Leave zero to use the bank default sale-ban fee.",
    )
    notes = fields.Char()

    @api.depends("min_downpayment_pct", "max_downpayment_pct", "min_term_months", "max_term_months", "annual_interest_rate")
    def _compute_name(self):
        for rec in self:
            rec.name = _("DP %(min)s-%(max)s%% | %(t1)s-%(t2)s months | %(rate)s%%") % {
                "min": rec.min_downpayment_pct,
                "max": rec.max_downpayment_pct,
                "t1": rec.min_term_months,
                "t2": rec.max_term_months,
                "rate": rec.annual_interest_rate,
            }

    @api.constrains("min_downpayment_pct", "max_downpayment_pct", "min_term_months", "max_term_months", "annual_interest_rate")
    def _check_rate_ranges(self):
        for rec in self:
            if rec.min_downpayment_pct < 0 or rec.max_downpayment_pct > 100 or rec.min_downpayment_pct > rec.max_downpayment_pct:
                raise ValidationError(_("Rate down payment range is invalid."))
            if rec.min_term_months <= 0 or rec.max_term_months < rec.min_term_months:
                raise ValidationError(_("Rate term range is invalid."))
            if rec.annual_interest_rate < 0:
                raise ValidationError(_("Interest rate cannot be negative."))


class BankOfferAssessment(models.Model):
    _name = "bank.offer.assessment"
    _description = "Bank Financing Pre-Assessment"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(default=lambda self: _("New"), copy=False, readonly=True)
    user_id = fields.Many2one("res.users", default=lambda self: self.env.user, required=True, readonly=True)
    customer_name = fields.Char(required=True, tracking=True)
    phone = fields.Char()
    monthly_income = fields.Monetary(required=True, tracking=True)
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id.id,
        required=True,
    )
    job_type_id = fields.Many2one("bank.offer.job.type", required=True, tracking=True)
    age = fields.Integer(required=True, tracking=True)
    vehicle_type = fields.Selection([
        ("new", "New"),
        ("used", "Used"),
        ("electric", "Electric"),
        ("commercial", "Commercial / Van / Truck"),
    ], default="new", required=True, tracking=True)
    vehicle_model_year = fields.Integer(string="Vehicle Model Year")
    car_price = fields.Monetary(required=True, tracking=True)
    down_payment = fields.Monetary(required=True, tracking=True)
    downpayment_pct = fields.Float(compute="_compute_financing", store=True)
    finance_amount = fields.Monetary(compute="_compute_financing", store=True)
    term_months = fields.Integer(default=60, required=True, tracking=True)
    assessment_date = fields.Date(default=fields.Date.context_today, required=True)
    state = fields.Selection([
        ("draft", "Draft"),
        ("calculated", "Calculated"),
    ], default="draft", required=True, tracking=True)
    result_ids = fields.One2many("bank.offer.assessment.result", "assessment_id", string="Recommended Offers", copy=False)
    eligible_count = fields.Integer(readonly=True)
    notes = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("bank.offer.assessment") or _("New")
        return super().create(vals_list)

    @api.depends("car_price", "down_payment")
    def _compute_financing(self):
        for rec in self:
            rec.finance_amount = max((rec.car_price or 0.0) - (rec.down_payment or 0.0), 0.0)
            rec.downpayment_pct = (rec.down_payment / rec.car_price * 100.0) if rec.car_price else 0.0

    @api.constrains("age", "monthly_income", "car_price", "down_payment", "term_months")
    def _check_input(self):
        for rec in self:
            if rec.age <= 0:
                raise ValidationError(_("Customer age must be greater than zero."))
            if rec.monthly_income <= 0:
                raise ValidationError(_("Monthly income must be greater than zero."))
            if rec.car_price <= 0:
                raise ValidationError(_("Vehicle price must be greater than zero."))
            if rec.down_payment < 0 or rec.down_payment >= rec.car_price:
                raise ValidationError(_("Down payment must be zero or more and less than the vehicle price."))
            if rec.term_months <= 0:
                raise ValidationError(_("Financing term must be greater than zero."))

    def _monthly_installment(self, principal, annual_rate, months, method):
        if months <= 0:
            return 0.0
        if not annual_rate:
            return principal / months
        if method == "reducing":
            monthly_rate = annual_rate / 100.0 / 12.0
            factor = pow(1.0 + monthly_rate, months)
            return principal * monthly_rate * factor / (factor - 1.0)
        total_interest = principal * (annual_rate / 100.0) * (months / 12.0)
        return (principal + total_interest) / months

    def _program_rejection_reason(self, program):
        self.ensure_one()
        today = self.assessment_date or fields.Date.context_today(self)
        if program.effective_from and today < program.effective_from:
            return _("Program is not effective yet")
        if program.effective_to and today > program.effective_to:
            return _("Program has expired")
        if self.downpayment_pct + 1e-6 < program.min_downpayment_pct or self.downpayment_pct - 1e-6 > program.max_downpayment_pct:
            return _("Down payment percentage is outside the program range")
        if self.term_months < program.min_term_months or self.term_months > program.max_term_months:
            return _("Requested term is outside the program range")
        if self.age < program.min_customer_age:
            return _("Customer age is below the minimum")
        if program.max_customer_age and self.age > program.max_customer_age:
            return _("Customer age exceeds the maximum")
        if program.max_age_at_end and (self.age + self.term_months / 12.0) > program.max_age_at_end:
            return _("Customer age at the end of finance exceeds the allowed maximum")
        if self.monthly_income < program.min_monthly_income:
            return _("Monthly income is below the minimum")
        if program.max_car_price and self.car_price > program.max_car_price:
            return _("Vehicle price exceeds the maximum")
        if program.min_finance_amount and self.finance_amount < program.min_finance_amount:
            return _("Finance amount is below the minimum")
        if program.max_finance_amount and self.finance_amount > program.max_finance_amount:
            return _("Finance amount exceeds the maximum")
        if program.vehicle_type != "any" and self.vehicle_type != program.vehicle_type:
            return _("Vehicle type is not supported")
        if self.vehicle_type == "used" and program.used_vehicle_min_year and self.vehicle_model_year and self.vehicle_model_year < program.used_vehicle_min_year:
            return _("Vehicle model year is older than the program allows")
        if program.accepted_job_type_ids and self.job_type_id not in program.accepted_job_type_ids:
            return _("Customer job type is not accepted by this program")
        # Imported sheets encode the customer job in the program name.  If no
        # explicit Many2many was imported, honor that source information too.
        if not program.accepted_job_type_ids:
            parsed = program._parsed_import_values()
            if parsed["job_xmlid"]:
                inferred_job = self.env.ref(parsed["job_xmlid"], raise_if_not_found=False)
                if inferred_job and self.job_type_id != inferred_job:
                    return _("Customer job type is not accepted by this program")
        return False

    def action_calculate(self):
        Result = self.env["bank.offer.assessment.result"]
        Program = self.env["bank.offer.program"]
        for rec in self:
            rec._check_input()
            rec.result_ids.unlink()
            candidates = []
            programs = Program.search([("active", "=", True), ("bank_id.active", "=", True)])
            for program in programs:
                # Imported financing sheets may contain the rate inside the
                # program name rather than as a separate One2many rate row.
                # Build that missing rate automatically so every valid bank can
                # participate in the comparison.
                program._ensure_imported_rate()
                reason = rec._program_rejection_reason(program)
                if reason:
                    continue
                rate = program.rate_line_ids.filtered(
                    lambda r: r.active
                    and rec.downpayment_pct + 1e-6 >= r.min_downpayment_pct
                    and rec.downpayment_pct - 1e-6 <= r.max_downpayment_pct
                    and rec.term_months >= r.min_term_months
                    and rec.term_months <= r.max_term_months
                ).sorted(lambda r: (r.annual_interest_rate, r.id))[:1]
                if not rate:
                    continue
                rate = rate[0]
                monthly = rec._monthly_installment(
                    rec.finance_amount,
                    rate.annual_interest_rate,
                    rec.term_months,
                    rate.interest_method,
                )
                installment_pct = (monthly / rec.monthly_income * 100.0) if rec.monthly_income else 0.0
                if program.max_installment_income_pct and installment_pct > program.max_installment_income_pct:
                    continue
                sale_ban_fee = rate.sale_ban_fee or program.bank_id.sale_ban_fee
                admin_fee = rec.finance_amount * rate.admin_fee_pct / 100.0
                annual_insurance = rec.car_price * rate.insurance_rate_pct / 100.0
                candidates.append({
                    "program": program,
                    "rate": rate,
                    "monthly": monthly,
                    "installment_pct": installment_pct,
                    "sale_ban_fee": sale_ban_fee,
                    "admin_fee": admin_fee,
                    "annual_insurance": annual_insurance,
                })

            # Best financial offer first. Approval speed is a tie-breaker,
            # not the primary ranking criterion.
            candidates.sort(key=lambda c: (
                c["monthly"],
                c["rate"].annual_interest_rate,
                c["program"].approval_days,
                c["program"].bank_id.sequence,
            ))
            rec.eligible_count = len(candidates)
            # Show every eligible offer. The user can see the full market
            # comparison instead of only the first three records.
            for rank, c in enumerate(candidates, start=1):
                Result.create({
                    "assessment_id": rec.id,
                    "rank": rank,
                    "bank_id": c["program"].bank_id.id,
                    "program_id": c["program"].id,
                    "rate_id": c["rate"].id,
                    "annual_interest_rate": c["rate"].annual_interest_rate,
                    "interest_method": c["rate"].interest_method,
                    "monthly_installment": c["monthly"],
                    "installment_income_pct": c["installment_pct"],
                    "approval_days": c["program"].approval_days,
                    "insurance_required": c["rate"].insurance_required,
                    "insurance_rate_pct": c["rate"].insurance_rate_pct,
                    "annual_insurance_amount": c["annual_insurance"],
                    "admin_fee": c["admin_fee"],
                    "sale_ban_fee": c["sale_ban_fee"],
                })
            rec.state = "calculated"
        return True

    def action_reset_draft(self):
        for rec in self:
            rec.result_ids.unlink()
            rec.eligible_count = 0
            rec.state = "draft"
        return True


class BankOfferAssessmentResult(models.Model):
    _name = "bank.offer.assessment.result"
    _description = "Bank Financing Recommendation"
    _order = "rank, monthly_installment"

    assessment_id = fields.Many2one("bank.offer.assessment", required=True, ondelete="cascade")
    currency_id = fields.Many2one(related="assessment_id.currency_id", store=True, readonly=True)
    rank = fields.Integer(required=True)
    bank_id = fields.Many2one("bank.offer.bank", required=True, readonly=True)
    program_id = fields.Many2one("bank.offer.program", required=True, readonly=True)
    rate_id = fields.Many2one("bank.offer.rate", required=True, readonly=True)
    annual_interest_rate = fields.Float(readonly=True)
    interest_method = fields.Selection([
        ("flat", "Flat Rate"),
        ("reducing", "Reducing Balance"),
    ], readonly=True)
    monthly_installment = fields.Monetary(readonly=True)
    installment_income_pct = fields.Float(string="Installment / Income %", readonly=True)
    approval_days = fields.Integer(readonly=True)
    insurance_required = fields.Boolean(readonly=True)
    insurance_rate_pct = fields.Float(readonly=True)
    annual_insurance_amount = fields.Monetary(readonly=True)
    admin_fee = fields.Monetary(readonly=True)
    sale_ban_fee = fields.Monetary(readonly=True)
