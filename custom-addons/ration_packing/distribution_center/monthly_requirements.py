from dateutil.relativedelta import relativedelta

from odoo import models, fields, api
from datetime import date
import calendar

class distributionMonthlyRequirement(models.Model):
    _name = 'distribution.monthly.req'
    _description = 'distribution Monthly Requirement'

    date = fields.Date()
    center_id = fields.Many2one('res.partner')

    MONTH_SELECTION = [
        ('01', 'January'), ('02', 'February'), ('03', 'March'),
        ('04', 'April'), ('05', 'May'), ('06', 'June'),
        ('07', 'July'), ('08', 'August'), ('09', 'September'),
        ('10', 'October'), ('11', 'November'), ('12', 'December'),
    ]

    month = fields.Selection(MONTH_SELECTION, required=True, string="Month")
    year = fields.Selection(
        [(str(y), str(y)) for y in range(2020, fields.Date.today().year + 1)],
        required=True,
        string="Year",
        default=lambda self: str(fields.Date.today().year),
    )

    line_ids = fields.One2many('distribution.monthly.line', 'req_id', string="Lines")

    state = fields.Selection(
        string='State',
        selection=[('inprocess', 'In Process'),
                   ('confirmed', 'Confirmed'), ],
        required=False, )


    def action_confirm(self):
        for wiz in self:
            req = self.env['ration.monthly.req'].create({
                'month': wiz.month,
                'center_id': wiz.center_id.id,
            })
            for line in wiz.line_ids:
                self.env['ration.monthly.line'].create({
                    'req_id': req.id,
                    'date': line.date,
                    'category_id': line.category_idd.id,
                    'donee': line.donee.id,
                    # 'quantity': line.quantity,
                    'product': line.product,
                })
        return {'type': 'ir.actions.act_window_close'}


    def _add_recurring_requirements(self):
        """
        Cron entry point: each run should roll forward to next month's first day,
        then propagate all approved recurring contracts and special approvals.
        """
        # 1. Determine the first day of next month
        today = fields.Date.context_today(self)
        next_month = today + relativedelta(months=1)
        first_next = next_month.replace(day=1)

        # 2. Fetch all recurring contracts approved by Welfare or Masajid/Madaris
        contracts = self.env['donee.contract'].search([
            ('recurring', '=', True),
            ('state', '=', 'approved'),
        ])

        # 3. For each contract, ensure a header exists and then add lines
        for contract in contracts:
            req = self.search([
                ('date', '=', first_next),
                ('center_id', '=', contract.center_id.id)
            ], limit=1)

            if not req:
                req = self.create({
                    'date': first_next,
                    'center_id': contract.center_id.id,
                })

            for c_line in contract.pack_line_ids:
                self.env['ration.monthly.line'].create({
                    'req_id': req.id,
                    'date': first_next + relativedelta(days=c_line.day-1) if hasattr(c_line, 'day') else first_next,
                    'category_id': c_line.category_id.id,
                    'quantity': c_line.quantity,
                })

        # 5. Handle special approvals similarly
        approvals = self.env['special.approval'].search([
            ('date', '=', first_next),
            ('state', '=', 'approved'),
        ])
        for app in approvals:
            req = self.search([
                ('date', '=', first_next),
                ('center_id', '=', app.center_id.id)
            ], limit=1) or self.create({
                'date': first_next,
                'center_id': app.center_id.id,
            })
            for line in app.pack_line_ids:
                self.env['ration.monthly.line'].create({
                    'req_id': req.id,
                    'date': first_next + relativedelta(days=line.day-1) if hasattr(line, 'day') else first_next,
                    'category_id': line.category_id.id,
                    'quantity': line.quantity,
                })

        return True


    # def action_confirm(self):
    #     for record in self:
    #         if record.state == 'inprocess':


class MonthlyLine(models.Model):
    _name = 'distribution.monthly.line'
    _description = 'distribution Monthly Requirement Line'

    req_id = fields.Many2one('distribution.monthly.req', ondelete='cascade')
    date = fields.Date(string="Date",)
    # category_id = fields.Many2one('ration.pack.category', string="Pack Category")

    category_idd = fields.Many2one('disbursement.category', string="Disbursement Category")
    product = fields.Many2many(
        comodel_name='product.product',
        string='Product',
        required=False)
    donee = fields.Many2one('res.partner', string="Donee")
    name = fields.Char(
        string='Voucher',
        required=False)

    disbursement_type_ids = fields.Many2many('disbursement.type', string="Disbursement Type ID", tracking=True)






