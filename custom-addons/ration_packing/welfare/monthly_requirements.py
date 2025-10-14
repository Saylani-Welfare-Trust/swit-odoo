from dateutil.relativedelta import relativedelta

from odoo import models, fields, api
from datetime import date
import calendar

from odoo import api, fields, models, exceptions, _


class welfareMonthlyRequirement(models.Model):
    _name = 'welfare.monthly.req'
    _description = 'welfare Monthly Requirement'

    center_id = fields.Many2one('res.partner', )
    line_ids = fields.One2many('welfare.monthly.line', 'req_id', string="Lines")
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

    state = fields.Selection(
        string='State',
        selection=[('inprocess', 'In Process'),
                   ('confirmed', 'Confirmed'), ],
        default='inprocess',
        required=False, )

    @api.onchange('month', 'year')
    def _onchange_month_year(self):
        if not (self.month and self.year):
            self.line_ids = [(5, 0, 0)]
            return

        y = int(self.year)
        m = int(self.month)
        first_day = date(y, m, 1)
        last_day = date(y, m, calendar.monthrange(y, m)[1])

        new_lines = [(5, 0, 0)]
        seen = set()

        # 1) grab all candidate lines
        req_lines = self.env['disbursement.request.line'].search([
            ('collection_date', '<=', last_day),
            ('disbursement_category_id.name', 'ilike', 'in kind'),
            ('disbursement_type_id.name', 'ilike', 'kifalat'),
        ])

        # 2) for each line, find its parent request exactly once
        for line in req_lines:
            # parent request
            parent = line.disbursement_request_id
            if not parent:
                continue

            # figure out which dates this line should contribute
            dates = []
            if line.order_type == 'one_time':
                if first_day <= line.collection_date <= last_day:
                    dates = [line.collection_date]
            else:
                raw = line.recurring_duration or '1_M'
                try:
                    months = int(raw.split('_', 1)[0])
                except ValueError:
                    raise exceptions.UserError(
                        _("Invalid recurring duration %s on %s") % (raw, parent.name))
                start_dt = line.collection_date
                end_dt = start_dt + relativedelta(months=months - 1)
                if start_dt <= last_day and end_dt >= first_day:
                    day = min(start_dt.day, calendar.monthrange(y, m)[1])
                    dates = [date(y, m, day)]

            for dt in dates:
                # build a dedupe key from immutable IDs
                key = (
                    parent.id,
                    line.id,
                    dt,
                )
                if key in seen:
                    continue
                seen.add(key)

                new_lines.append((0, 0, {
                    'date': dt,
                    'name': parent.name.id if isinstance(parent.name, models.Model) else parent.name,
                    'category_id': line.disbursement_category_id.id,
                    'donee': parent.donee_id.id,
                    'disbursement_type_ids': [(6, 0, line.disbursement_type_id.ids)],
                    'product': line.product_id,
                }))

        self.line_ids = new_lines

    def action_execute(self):
        """Push each monthly line into its own daily requirement record,
        grouping by date so there's only one record per date."""
        DailyReq = self.env['welfare.daily.req']

        for req in self:
            # Build a map: date → list of line dicts
            grouped = {}
            for mline in req.line_ids:
                d = mline.date
                # prepare your line values
                vals = {
                    'category_id': mline.category_id.id,
                    'donee': mline.donee.id,
                    'name': mline.name,
                    'quantity': mline.quantity,
                    'product': mline.product.ids if hasattr(mline, 'product') else False,
                    'disbursement_type_ids': [(6, 0, mline.disbursement_type_ids.ids)],
                }
                grouped.setdefault(d, []).append(vals)

            # Create one DailyReq per distinct date
            for d, lines in grouped.items():
                DailyReq.create({
                    'date': d,
                    'center_id': req.center_id.id,
                    'line_ids': [(0, 0, vals) for vals in lines],
                })

        # Optionally mark monthly plan as executed
        self.write({'state': 'confirmed'})
        return True

    def action_confirm(self):
        dist_obj = self.env['distribution.monthly.req']
        donee_obj = self.env['donee.contract']

        for record in self.filtered(lambda r: r.state == 'inprocess'):
            # 1) Build the manual distribution lines
            dist_lines = [
                (0, 0, {
                    'date': line.date,
                    'category_idd': line.category_id.id,
                    'donee': line.donee.id,
                    'product': line.product,

                    # 'quantity': line.quantity,
                })
                for line in record.line_ids
            ]

            # 2) Find approved recurring Donee Contracts
            recurring_contracts = donee_obj.search([
                # ('center_id', '=', record.center_id.id),
                ('recurring', '=', True),
                ('state', '=', 'approved'),
            ])

            # 3) Build the “donee” lines tuples for both Distribution and Welfare
            donee_lines = []
            for contract in recurring_contracts:
                for cl in contract.pack_line_ids:
                    # For Distribution
                    dist_lines.append((0, 0, {
                        'date': record.date,
                        'category_id': cl.category_id.id,
                        'donee': recurring_contracts.center_id.id,

                        'quantity': cl.quantity,
                    }))
                    # For Welfare record itself
                    donee_lines.append((0, 0, {
                        'date': record.date,
                        'category_id': cl.category_id.id,
                        'donee': recurring_contracts.center_id.id,
                        'product_id': cl.product_id,

                        'quantity': cl.quantity,
                    }))

            # 4) Create the Distribution record
            dist_obj.create({
                'month': record.month,
                'center_id': record.center_id.id,
                'line_ids': dist_lines,
            })

            # 5) Now update the Welfare record’s lines and state
            #    First, preserve existing manual lines as (4, id)
            existing_manual = [(4, l.id) for l in record.line_ids]

            #    Combine them with the new donee lines into one list
            all_welfare_lines = existing_manual + donee_lines

            record.write({
                'state': 'confirmed',
                'line_ids': all_welfare_lines,
            })

        return True


class MonthlyLine(models.Model):
    _name = 'welfare.monthly.line'
    _description = 'Monthly Requirement Line'

    req_id = fields.Many2one('welfare.monthly.req', ondelete='cascade')
    date = fields.Date(string="Date", )
    # category_id = fields.Many2one('ration.pack.category', string="Pack Category")
    # quantity = fields.Integer(string="Quantity")

    # product_id = fields.Char(
    #     related='category_id.product_id',
    #     string='Product_id',
    #     required=False)

    # donee = fields.Many2one(
    #     comodel_name='res.partner',
    #     string='Donee',
    #     domain="[('is_donee', '=', True)]",
    #     required=False)

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
