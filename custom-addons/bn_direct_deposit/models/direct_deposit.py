from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


status_selection = [       
    ('draft', 'Draft'),
    ('clear', 'Clear'),
    ('not_clear', 'Not Clear'),
]


class DirectDeposit(models.Model):
    _name = 'direct.deposit'
    _description = "Direct Deposit"


    donor_id = fields.Many2one('res.partner', string="Donor")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)

    name = fields.Char('Name', default="New")

    state = fields.Selection(selection=status_selection, string="Status", default="draft")

    amount = fields.Monetary('Amount', currency_field='currency_id')

    direct_deposit_line_ids = fields.One2many('direct.deposit.line', 'direct_deposit_id', string="Direct Deposit Lines")


    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('direct_deposit') or ('New')

        return super(DirectDeposit, self).create(vals)
    
    def calculate_amount(self):
        self.amount = sum(line.amount for line in self.direct_deposit_line_ids)

    @api.model
    def create_dd_record(self, data):
        # -------------------------
        # 1. Prepare Line Items
        # -------------------------
        product_lines = []
        for line in data['order_lines']:
            product_lines.append((0, 0, {
                'product_id': line['product_id'],
                'quantity': line['quantity'],
                'amount': line['price'],
            }))

        # -------------------------
        # 2. Create DHS Record
        # -------------------------
        dd = self.env['direct.deposit'].create({
            'donor_id': data['donor_id'],
            'direct_deposit_line_ids': product_lines,
        })

        # -------------------------
        # 3. Calculate prices & taxes for all lines
        # -------------------------
        for line in dd.donation_home_service_line_ids:
            base_price = line.product_id.lst_price
            taxes = line.product_id.taxes_id

            total_price_incl_tax = base_price
            for tax in taxes:
                if tax.amount_type == 'percent':
                    total_price_incl_tax += base_price * (tax.amount / 100)
                else:
                    total_price_incl_tax += tax.amount

            if not line.amount:
                line.amount = total_price_incl_tax * line.quantity

        # -------------------------
        # 4. Recalculate totals
        # -------------------------
        dd.calculate_amount()

        return {
            "status": "success"
        }