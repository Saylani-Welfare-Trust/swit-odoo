from odoo import models, fields, api
from datetime import timedelta

class distributionDailyRequirement(models.Model):
    _name = 'distribution.daily.req'
    _description = 'distribution Daily Requirement (from Monthly Plan)'

    date      = fields.Date(required=True, index=True)
    center_id = fields.Many2one('res.partner',)
    line_ids  = fields.One2many('distribution.daily.line', 'req_id', string="Lines")

    state = fields.Selection(
        string='State',
        selection=[('draft', 'Draft'),
                   ('sent_to_ration', 'Sent to Ration Packing'), ],
        default='draft',
        required=False, )


    def action_send_to_ration(self):
        for record in self:
            if record.state == 'draft':
                Dist = self.env['ration.daily.req']
                for rec in self.filtered(lambda r: r.state == 'draft'):
                    # build lines for distribution
                    dist_lines = [
                        (0, 0, {
                            # 'category_id': line.category_id.id,
                            # 'donee': line.donee.id,
                            'product': line.product.id,
                            'quantity': line.quantity,
                            # 'name': line.name,
                            # 'disbursement_type_ids': line.disbursement_type_ids,

                        })
                        for line in rec.line_ids
                    ]
                    # create the distribution record
                    Dist.create({
                        'date': rec.date,
                        'center_id': rec.center_id.id,
                        'line_ids': dist_lines,
                    })
                    # mark as sent
                    rec.state = 'sent_to_ration'
                return True



class DailyLine(models.Model):
    _name = 'distribution.daily.line'
    _description = 'distribution Daily Requirement Line'

    req_id      = fields.Many2one('distribution.daily.req', ondelete='cascade')
    # category_id = fields.Many2one('ration.pack.category', required=True)
    category_id = fields.Many2one('disbursement.category', string="Disbursement Category")
    product = fields.Many2one(
        comodel_name='product.product',
        string='Product',
        required=False)
    donee = fields.Many2one('res.partner', string="Donee")
    quantity = fields.Integer(string="Quantity")
    name = fields.Char(
        string='Voucher',
        required=False)

    disbursement_type_ids = fields.Many2many('disbursement.type', string="Disbursement Type ID", tracking=True)
