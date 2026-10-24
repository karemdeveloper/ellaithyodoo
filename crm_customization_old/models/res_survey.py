from odoo import models, fields, api

class ResSurvey(models.Model):
    _name = 'res.survey'
    _description = 'Customer Satisfaction Survey'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(string="Survey Name", tracking=True, readonly=True, copy=False, default='New')
    partner_id = fields.Many2one('res.partner', string="Customer")
    comment = fields.Text(string='Comment')

    q1_sales_person = fields.Selection([
        ('excellent', 'ممتاز'),
        ('average', 'متوسط'),
        ('bad', 'سيئ'),
    ], string="ما مدى رضائك عن موظف المبيعات؟", tracking=True)

    q2_paper_speed = fields.Selection([
        ('excellent', 'ممتاز'),
        ('average', 'متوسط'),
        ('bad', 'سيئ'),
    ], string="ما مدى رضائك عن سرعة إنهاء الأوراق الخاصة بالسيارة؟ و عن مندوب الترخيص إن وجد؟", tracking=True)

    q3_insurance = fields.Selection([
        ('excellent', 'ممتاز'),
        ('average', 'متوسط'),
        ('bad', 'سيئ'),
        ('not_from_company', 'لم يتم التأمين من خلال الليثي أوتو جروب'),
    ], string="ما مدى رضائك عن موظف التأمين إن وجد؟", tracking=True)

    q4_used_car = fields.Selection([
        ('excellent', 'ممتاز'),
        ('average', 'متوسط'),
        ('bad', 'سيئ'),
        ('not_exchanged', 'لم أقم باستبدال سيارة قديمة'),
    ], string="فى حالة استبدال سيارتك القديمه بسيارة جديده من خلال الليثي أوتو جروب – ما مدى رضائك عن موظف المستعمل؟", tracking=True)

    q5_offer_shown = fields.Selection([
        ('yes', 'نعم'),
        ('no', 'لا'),
    ], string="هل تم عرض خصومات الحماية و الصيانة؟", tracking=True)

    q6_tip_request = fields.Selection([
        ('yes', 'نعم'),
        ('no', 'لا'),
    ], string="هل طلب منك اي إكراميات خلال تعاملك مع الليثي أوتو جروب؟", tracking=True)

    q6_person_name = fields.Char(
        string="في حالة الإجابة بنعم، أذكر اسم الشخص",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Generate sequence for survey name on creation"""
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('res.survey') or 'New'
        return super(ResSurvey, self).create(vals_list)
