from odoo import models, fields, api
from datetime import timedelta

class DailyRequirement(models.Model):
    _name = 'welfare.daily.req'
    _description = 'Daily Requirement (from Monthly Plan)'

    date      = fields.Date(required=True, index=True)
    center_id = fields.Many2one('res.partner',)
    line_ids  = fields.One2many('welfare.daily.line', 'req_id', string="Lines")

    MONTH_SELECTION = [
        ('01', 'January'), ('02', 'February'), ('03', 'March'),
        ('04', 'April'), ('05', 'May'), ('06', 'June'),
        ('07', 'July'), ('08', 'August'), ('09', 'September'),
        ('10', 'October'), ('11', 'November'), ('12', 'December'),
    ]

    month = fields.Selection(MONTH_SELECTION, string="Month")
    year = fields.Selection(
        [(str(y), str(y)) for y in range(2020, fields.Date.today().year + 1)],
        # required=True,
        string="Year",
        default=lambda self: str(fields.Date.today().year),
    )
    state = fields.Selection(
        string='State',
        selection=[('draft', 'Draft'),
                   ('sent_to_distribution', 'Sent to Distribution'), ],
        default='draft',
        required=False, )




    def action_send_to_distribution(self):
        for record in self:
            if record.state == 'draft':
                Dist = self.env['distribution.daily.req']
                for rec in self.filtered(lambda r: r.state == 'draft'):
                    # build lines for distribution
                    dist_lines = [
                        (0, 0, {
                            'quantity': line.quantity,
                            'category_id': line.category_id.id,
                            'name': line.name,
                            'donee': line.donee.id,
                            'product': line.product,
                            'disbursement_type_ids': line.disbursement_type_ids,
                        })
                        for line in rec.line_ids
                    ]
                    # create the distribution record
                    Dist.create({
                        'date': rec.date,
                        # 'year': rec.year,
                        'center_id': rec.center_id.id,
                        'line_ids': dist_lines,
                    })
                    # mark as sent
                    rec.state = 'sent_to_distribution'
                return True




class DailyLine(models.Model):
    _name = 'welfare.daily.line'
    _description = 'Daily Requirement Line'

    req_id      = fields.Many2one('welfare.daily.req', ondelete='cascade')
    date = fields.Date(string="Date", )


    category_id = fields.Many2one('disbursement.category', string="Disbursement Category")
    product = fields.Many2many(
        comodel_name='product.product',
        string='Product',
        required=False)
    donee = fields.Many2one('res.partner', string="Donee")
    quantity = fields.Integer(string="Quantity")
    name = fields.Char(
        string='Voucher',
        required=False)

    disbursement_type_ids = fields.Many2many('disbursement.type', string="Disbursement Type ID", tracking=True)
