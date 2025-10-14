from odoo import models, fields, api
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

import calendar
from odoo import api, fields, models, exceptions, _


class branch_request_for_kitchen(models.Model):
    _name = 'branch.kitchen.request'
    _description = 'Branch Request Monthly Cooked Food Menu'
    _rec_name = 'menu_month'

    MONTHS = [
        ('1', 'January'),
        ('2', 'February'),
        ('3', 'March'),
        ('4', 'April'),
        ('5', 'May'),
        ('6', 'June'),
        ('7', 'July'),
        ('8', 'August'),
        ('9', 'September'),
        ('10', 'October'),
        ('11', 'November'),
        ('12', 'December'),
    ]

    # store as string keys '1'..'12'; default to current month
    menu_month = fields.Selection(
        selection=MONTHS,
        string='Menu For Month',
        required=True,
        default=lambda self: str(datetime.now().month),
    )

    year = fields.Selection(
        [(str(y), str(y)) for y in range(2020, fields.Date.today().year + 1)],
        required=True,
        string="Year",
        default=lambda self: str(fields.Date.today().year),
    )

    line_ids = fields.One2many(
        comodel_name='branch.kitchen.request.line',
        inverse_name='menu_id',
        string='Menu Items',
    )
    state = fields.Selection(
        [('draft', 'Draft'), ('sent', 'Done')],
        default='draft',
        string='Status',
        copy=False,
    )

    mr_id = fields.Many2one('kitchen.material.requisition', string='Material Requisition')

    @api.onchange('menu_month', 'year')
    def _onchange_month_year(self):
        if not (self.menu_month and self.year):
            self.line_ids = [(5, 0, 0)]
            return

        y = int(self.year)
        m = int(self.menu_month)
        first_day = date(y, m, 1)
        last_day = date(y, m, calendar.monthrange(y, m)[1])

        new_lines = [(5, 0, 0)]

        # — Section 1: disbursement.request.line logic unchanged —
        req_lines = self.env['disbursement.request.line'].search([
            ('collection_date', '<=', last_day),
            ('disbursement_category_id.name', 'ilike', 'in kind'),
            ('disbursement_type_id.name', 'ilike', 'marriage / wedding'),
        ])
        main_reqs = self.env['disbursement.request'].search([
            ('disbursement_request_line_ids', 'in', req_lines.ids)
        ])
        for req in main_reqs:
            for line in req_lines:
                if line.order_type == 'one_time':
                    if first_day <= line.collection_date <= last_day:
                        new_lines.append((0, 0, {
                            'date': line.collection_date,
                            'name': req.name,
                            'category_id': line.disbursement_category_id.id,
                            'donee': req.donee_id.id,
                            'disbursement_type_ids': [(6, 0, line.disbursement_type_id.ids)],
                            'product_id': line.product_id.id,
                            'branch_name': line.branch_id.id,
                            'quantity': 1,
                            'requirement_from': 'Welfare',
                        }))
                else:
                    raw = line.recurring_duration or '1_M'
                    try:
                        months = int(raw.split('_', 1)[0])
                    except ValueError:
                        raise exceptions.UserError(
                            _("Invalid recurring duration %s on %s") % (raw, req.name))
                    start_dt = line.collection_date
                    end_dt = start_dt + relativedelta(months=months - 1)
                    if start_dt <= last_day and end_dt >= first_day:
                        day = min(start_dt.day, calendar.monthrange(y, m)[1])
                        recur_date = date(y, m, day)
                        new_lines.append((0, 0, {
                            'date': recur_date,
                            'name': req.name,
                            'category_id': line.disbursement_category_id.id,
                            'donee': req.donee_id.id,
                            'disbursement_type_ids': [(6, 0, line.disbursement_type_id.ids)],
                            'product_id': line.product_id.id,
                            'branch_name': line.branch_id.id,
                            'quantity': 1,
                            'requirement_from': 'Welfare',

                        }))

        # — Section 2: pull from ALL branch.request records for this month/year —
        branch_reqs = self.env['branch.request'].search([
            ('menu_month', '=', m),
            ('year', '=', y),
        ])
        for br in branch_reqs:
            for line in br.line_ids:
                new_lines.append((0, 0, {
                    'date': line.date,
                    'name': line.name.id,
                    'product_id': line.product_id,
                    'branch_name': br.branch_name.id,
                    'quantity': line.quantity,
                    'requirement_from': 'branch',

                }))

        self.line_ids = new_lines

    # @api.onchange('menu_month', 'year')
    def _onchange_month_yearrr(self):
        # if any key is missing, clear lines
        if not (self.menu_month and self.year):
            self.line_ids = [(5, 0, 0)]
            return

        y = int(self.year)
        m = int(self.menu_month)
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

        print('reqs', reqs)

        main_req = self.env['disbursement.request'].search([('disbursement_request_line_ids', 'in', reqs.ids)])

        print('main_re', main_req)

        for req in main_req:
            for line in reqs:
                if line.order_type == 'one_time':
                    # include only if within the month
                    if first_day <= line.collection_date <= last_day:
                        new_lines.append((0, 0, {
                            'date': line.collection_date,
                            'name': req.name,
                            'category_id': line.disbursement_category_id.id,
                            'donee': req.donee_id.id,
                            'disbursement_type_ids': [(6, 0, line.disbursement_type_id.ids)],
                            'product_id': line.product_id,
                        }))
                else:  # recurring
                    # parse "6_M" → 6
                    raw = line.recurring_duration or '1_M'
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
                            'disbursement_type_ids': [(6, 0, line.disbursement_type_id.ids)],
                            'product_id': line.product_id,
                        }))

        self.line_ids = new_lines

    def action_execute_daily_requirement(self):
        """Create daily kitchen request lines based on the selected date in branch.kitchen.request.line"""
        self.ensure_one()

        DailyRequest = self.env['kitchen.daily.request']
        DailyRequestLine = self.env['kitchen.daily.request.line']

        for line in self.line_ids:
            if line.date:
                daily_request = DailyRequest.create({
                    'date': line.date,
                    'branch_id': line.branch_name.id,
                    'request_line_ids': [(0, 0, {
                        'product_id': line.product_id.id,
                        'quantity': line.quantity,
                        'menu_name_id': line.name.id,
                    })],
                })

    def action_issue_mr(self):
        self.ensure_one()
        # Create the requisition header
        mr = self.env['kitchen.material.requisition'].create({
            'request_id': self.id,
            'line_ids': [
                (0, 0, {
                    'product_id': line.product_id.id,
                    'branch_name': line.branch_name.id,
                    'quantity': line.quantity,
                    # 'uom_id': line.product_id.uom_id.id,
                })
                for line in self.line_ids
            ],
        })
        self.write({'state': 'sent', 'mr_id': mr.id})
        mr._process_requisition()


class KitchenMenuLine(models.Model):
    _name = 'branch.kitchen.request.line'
    _description = 'Menu Item'

    menu_id = fields.Many2one('branch.kitchen.request', required=True, ondelete='cascade')

    requirement_from = fields.Selection(
        string='Requirement From',
        selection=[('branch', 'branch'),
                   ('Welfare', 'Welfare'), ],
        required=False, )


    date = fields.Date(
        string='Date',
        required=False)

    name = fields.Many2one('kitchen.menu', string='Menu Name')

    product_id = fields.Many2one('product.product', string='Dish', required=True)

    @api.onchange('name')
    def _onchange_name(self):
        for rec in self:
            if rec.name and rec.name.name:
                # assuming `kitchen.menu` has a m2o field `name` pointing to product.product`
                rec.product_id = rec.name.name.id
            else:
                rec.product_id = False




    donee = fields.Many2one('res.partner', string="Donee")

    category_id = fields.Many2one('disbursement.category', string="Disbursement Category")

    disbursement_type_ids = fields.Many2many('disbursement.type', string="Disbursement Type ID", tracking=True)



    branch_name = fields.Many2one(
        comodel_name='res.company',
        string='Branch Name',
        required=False)

    quantity = fields.Float(
        string='Quantity',
        required=False)
