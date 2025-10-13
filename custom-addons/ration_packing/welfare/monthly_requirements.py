from collections import defaultdict

from dateutil.relativedelta import relativedelta

from odoo import models, fields, api
from datetime import date
import calendar

from odoo import api, fields, models, exceptions, _
from odoo.exceptions import UserError


class welfareMonthlyRequirement(models.Model):
    _name = 'welfare.monthly.req'
    _description = 'welfare Monthly Requirement'

    center_id = fields.Many2one('res.partner', )
    line_ids = fields.One2many('welfare.monthly.line', 'req_id', string="Lines")
    products = fields.Many2many('product.product', string="Products")
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

    def action_create_purchase_request(self):
        """Create a grouped Purchase Request from this monthly requirement.

        Behavior:
        - Sum quantities per product from monthly lines (use line.quantity if set, otherwise default to 1).
        - Also include any products selected on the main record (products many2many) if they are not already present in lines (quantity default 1).
        - Create one purchase.request and one purchase.request.line per product with the aggregated quantity.
        """
        PurchaseRequest = self.env['purchase.request']
        PurchaseRequestLine = self.env['purchase.request.line']

        for rec in self:
            # ensure there is something to create
            if not rec.line_ids and not rec.products:
                raise exceptions.UserError("No lines or products to create purchase request.")

            # Step 1: Group products with total quantity
            product_quantities = defaultdict(float)
            product_uom = {}
            product_names = {}
            date_required_map = {}

            # Aggregate from monthly lines first (use explicit quantities on lines)
            for line in rec.line_ids:
                prod = line.product
                if not prod:
                    continue
                qty = float(line.expected_qty or 1.0)
                product_quantities[prod.id] += qty
                product_uom[prod.id] = prod.uom_id.id if prod.uom_id else False
                product_names[prod.id] = line.name or prod.display_name
                # keep the latest date among lines for that product
                if line.date:
                    prev_date = date_required_map.get(prod.id)
                    if not prev_date or line.date > prev_date:
                        date_required_map[prod.id] = line.date

            # Include any explicitly selected products on the main record
            for prod in rec.products:
                if prod.id not in product_quantities:
                    # default qty for selected products without lines = 1
                    product_quantities[prod.id] += 1.0
                    product_uom[prod.id] = prod.uom_id.id if prod.uom_id else False
                    product_names[prod.id] = prod.name
                    date_required_map[prod.id] = date_required_map.get(prod.id, fields.Date.today())

            # Step 2: Create the Purchase Request header
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
                    'product_id': int(product_id),
                    'product_qty': float(total_qty),
                    'product_uom_id': product_uom.get(product_id) or False,
                    'description': product_names.get(product_id, ""),
                    'date_required': date_required_map.get(product_id, fields.Date.today()),
                })

        return True

    state = fields.Selection(
        string='State',
        selection=[('inprocess', 'In Process'),
                   ('confirmed', 'Confirmed'), ],
        default='inprocess',
        required=False, )

    @api.onchange('month', 'year', 'products')
    def _onchange_month_year(self):
        if not (self.month and self.year):
            self.line_ids = [(5, 0, 0)]
            return

        y = int(self.year)
        m = int(self.month)
        first_day = date(y, m, 1)
        last_day = date(y, m, calendar.monthrange(y, m)[1])

        grouped = defaultdict(float)  # (date, product_id) -> total_qty_for_that_date
        meta = {}

        domain = [
            ('collection_date', '<=', last_day),
            ('disbursement_category_id.name', 'ilike', 'in kind'),
            ('disbursement_type_id.name', 'ilike', 'kifalat'),
        ]
        if self.products:
            domain.append(('product_id', 'in', self.products.ids))

        req_lines = self.env['disbursement.request.line'].search(domain)
        parent_reqs = self.env['disbursement.request'].search([('disbursement_request_line_ids', 'in', req_lines.ids)])

        for req in parent_reqs:
            for line in req.disbursement_request_line_ids:
                product = getattr(line, 'product_id', None) or getattr(line, 'product', None)
                if not product:
                    continue
                if self.products and product.id not in self.products.ids:
                    continue

                if getattr(line, 'order_type', 'one_time') == 'one_time':
                    if first_day <= line.collection_date <= last_day:
                        date_for_line = line.collection_date
                        qty = getattr(line, 'quantity', None) or getattr(line, 'product_qty', None) or getattr(line,
                                                                                                               'product_uom_qty',
                                                                                                               1.0)
                        key = (date_for_line, product.id)
                        grouped[key] += float(qty)
                        meta[key] = {
                            'category_id': getattr(line, 'disbursement_category_id',
                                                   False) and line.disbursement_category_id.id,
                        }
                else:
                    raw = getattr(line, 'recurring_duration', None) or '1_M'
                    try:
                        months = int(raw.split('_', 1)[0])
                    except (ValueError, Exception):
                        raise exceptions.UserError(_("Invalid recurring duration %s on %s") % (raw, req.name))
                    start_dt = line.collection_date
                    end_dt = start_dt + relativedelta(months=months - 1)
                    if start_dt <= last_day and end_dt >= first_day:
                        day = min(start_dt.day, calendar.monthrange(y, m)[1])
                        recur_date = date(y, m, day)
                        qty = getattr(line, 'quantity', None) or getattr(line, 'product_qty', None) or getattr(line,
                                                                                                               'product_uom_qty',
                                                                                                               1.0)
                        key = (recur_date, product.id)
                        grouped[key] += float(qty)
                        meta[key] = {
                            'category_id': getattr(line, 'disbursement_category_id',
                                                   False) and line.disbursement_category_id.id,
                        }

        new_lines = [(5, 0, 0)]
        DisbLine = self.env['disbursement.request.line']
        for (dt, prod_id), total_qty in sorted(grouped.items()):
            # received_qty = sum of quantities for this product up to this date (<= dt)
            received_search_domain = [
                ('product_id', '=', prod_id),
                ('collection_date', '<=', dt),
            ]
            received_lines = DisbLine.search(received_search_domain)
            received_qty = sum(
                float(
                    getattr(rl, 'quantity', None) or getattr(rl, 'product_qty', None) or getattr(rl, 'product_uom_qty',
                                                                                                 1.0))
                for rl in received_lines
            )

            # prev month same date qty
            prev_dt = dt - relativedelta(months=1)
            last_prev_month_day = calendar.monthrange(prev_dt.year, prev_dt.month)[1]
            prev_day = min(dt.day, last_prev_month_day)
            prev_date = date(prev_dt.year, prev_dt.month, prev_day)

            expected_search_domain = [
                ('product_id', '=', prod_id),
                ('collection_date', '=', prev_date),
            ]
            expected_lines = DisbLine.search(expected_search_domain)
            prev_month_qty = sum(
                float(
                    getattr(el, 'quantity', None) or getattr(el, 'product_qty', None) or getattr(el, 'product_uom_qty',
                                                                                                 1.0))
                for el in expected_lines
            )

            # new logic: expected = received + prev month qty
            expected_qty = received_qty + prev_month_qty

            new_lines.append((0, 0, {
                'date': dt,
                'product': prod_id,
                'quantity': total_qty,
                'received_qty': received_qty,
                'expected_qty': expected_qty,
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
                    'quantity': mline.expected_qty,
                    'product': mline.product.id if hasattr(mline, 'product') else False,
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

    # NEW fields
    received_qty = fields.Float(string="Received Qty", digits=(16, 2), readonly=True)
    expected_qty = fields.Float(string="Expected Qty (prev month same day)", digits=(16, 2), readonly=True)
