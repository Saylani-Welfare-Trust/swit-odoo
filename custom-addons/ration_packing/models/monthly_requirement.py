from collections import defaultdict

from dateutil.relativedelta import relativedelta

from odoo import models, fields, api
from datetime import date
import calendar
from datetime import datetime
from odoo import api, fields, models, exceptions, _
from odoo.exceptions import UserError


class MonthlyRequirement(models.Model):
    _name = 'ration.monthly.req'
    _description = 'Monthly Requirement'

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
    center_id = fields.Many2one('res.partner',)
    line_ids = fields.One2many('ration.monthly.line', 'req_id', string="Lines")

    def action_create_purchase_request(self):
        PurchaseRequest = self.env['purchase.request']
        PurchaseRequestLine = self.env['purchase.request.line']

        for rec in self:
            if not rec.line_ids:
                raise UserError("No lines to create purchase request.")

            # Step 1: Group products with total quantity
            product_quantities = defaultdict(int)  # product_id => total_quantity
            product_uom = {}  # product_id => uom_id
            product_names = {}  # product_id => description (optional)

            for line in rec.line_ids:
                for product in line.product:
                    product_quantities[product.id] += 1  # Always count as 1 per product per line
                    product_uom[product.id] = product.uom_id.id
                    product_names[product.id] = line.name or product.name

            # Step 2: Create the Purchase Request
            purchase_req = PurchaseRequest.create({
                'origin': f"Monthly Requirement {rec.month}-{rec.year}",
                'date_start': fields.Date.today(),
                'requested_by': self.env.user.id,
                'description': f'Purchase Request for {rec.center_id.name or "N/A"} - {rec.month}-{rec.year}',
            })

            # Step 3: Create grouped lines
            for product_id, total_qty in product_quantities.items():
                PurchaseRequestLine.create({
                    'request_id': purchase_req.id,
                    'product_id': product_id,
                    'product_qty': total_qty,
                    'product_uom_id': product_uom[product_id],
                    'description': product_names[product_id],
                    'date_required': fields.Date.today(),  # You could also get latest line.date if needed
                })

        return True

    @api.onchange('month', 'year')
    def _onchange_month_year(self):
        # if any key is missing, clear lines
        if not (self.month and self.year):
            self.line_ids = [(5, 0, 0)]
            return

        y = int(self.year)
        m = int(self.month)
        first_day = date(y, m, 1)
        last_day = date(y, m, calendar.monthrange(y, m)[1])

        # clear existing
        new_lines = [(5, 0, 0)]

        # Gather all requests that start on/before last_day and match the center
        reqs = self.env['disbursement.request.line'].search([
            ('collection_date', '<=', last_day),
            ('disbursement_category_id.name', 'ilike', 'in kind'),
            ('disbursement_type_id.name', 'ilike', 'kifalat'),
            # ('branch_id', '=', self.center_id.id),
        ])


        main_req = self.env['disbursement.request'].search([('disbursement_request_line_ids', 'in', reqs.ids)])


        for req in main_req:
            for line in req.disbursement_request_line_ids:
                if line.order_type == 'one_time':
                    # include only if within the month
                    if first_day <= line.collection_date <= last_day:
                        new_lines.append((0, 0, {
                            'date': line.collection_date,
                            'name': req.name,
                            'category_id': line.disbursement_category_id.id,
                            'donee': req.donee_id.id,
                            'disbursement_type_ids': [(6, 0, line.disbursement_type_ids.ids)],
                            'product': line.disbursement_type_ids.mapped('product_id').ids,
                        }))
                else:  # recurring
                    # parse "6_M" → 6
                    raw = req.recurring_duration or '1_M'
                    try:
                        months = int(raw.split('_', 1)[0])
                    except ValueError:
                        raise exceptions.UserError(
                            _("Invalid recurring duration %s on %s") % (raw, req.name))
                    start_dt = line.collection_date
                    end_dt = start_dt + relativedelta(months=months - 1)

                    # if the selected month overlaps [start_dt, end_dt]
                    if start_dt <= last_day and end_dt >= first_day:
                        # build a date in this month with same day (capped to month-end)
                        day = min(start_dt.day, calendar.monthrange(y, m)[1])
                        recur_date = date(y, m, day)
                        new_lines.append((0, 0, {
                            'date': recur_date,
                            'name': req.name,
                            'category_id': line.disbursement_category_id.id,
                            'donee': req.donee_id.id,
                            'disbursement_type_ids': [(6, 0, line.disbursement_type_ids.ids)],
                            'product': line.disbursement_type_ids.mapped('product_id').ids,
                        }))

        self.line_ids = new_lines


class MonthlyLine(models.Model):
    _name = 'ration.monthly.line'
    _description = 'Monthly Requirement Line'

    req_id = fields.Many2one('ration.monthly.req', ondelete='cascade')
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


class MonthlyWizard(models.TransientModel):
    _name = 'ration.monthly.wizard'
    _description = 'Monthly Requirement Wizard'

    month_date = fields.Date(
        string="Month",
        default=lambda self: (fields.Date.context_today(self) + relativedelta(months=1)).replace(day=1)
    )
    center_id = fields.Many2one('res.partner', string="Distribution Center", required=True)
    line_ids = fields.One2many(
        'ration.monthly.wizard.line', 'wizard_id',
        string="Day‑Wise Lines", copy=False
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        mdate = res.get('month_date') or date.today().replace(day=1)
        year, month = fields.Date.from_string(mdate).year, fields.Date.from_string(mdate).month
        num_days = calendar.monthrange(year, month)[1]
        lines = []
        categories = self.env['ration.pack.category'].search([])
        for day in range(1, num_days + 1):
            for cat in categories:
                lines.append((0, 0, {
                    'date': fields.Date.add(mdate, days=day - 1),
                    'category_id': cat.id,
                    'quantity': 0,
                }))
        res['line_ids'] = lines
        return res

    def action_confirm(self):
        for wiz in self:
            req = self.env['ration.monthly.req'].create({
                'date': wiz.month_date,
                'center_id': wiz.center_id.id,
            })
            for line in wiz.line_ids:
                self.env['ration.monthly.line'].create({
                    'req_id': req.id,
                    'date': line.date,
                    'category_id': line.category_id.id,
                    'donee': line.donee.id,
                    'quantity': line.quantity,
                })
        return {'type': 'ir.actions.act_window_close'}


class MonthlyWizardLine(models.TransientModel):
    _name = 'ration.monthly.wizard.line'
    _description = 'Wizard Line for Monthly Requirement'

    wizard_id = fields.Many2one('ration.monthly.wizard', ondelete='cascade')
    date = fields.Date(string="Date", readonly=True)
    category_id = fields.Many2one('ration.pack.category', string="Pack Category", readonly=True)
    quantity = fields.Float(string="Quantity")

    donee = fields.Many2one(
        comodel_name='res.partner',
        string='Donee',
        domain="[('is_donee', '=', True)]",
        required=False)
