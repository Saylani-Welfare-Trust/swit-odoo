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

    move_id = fields.Many2one('account.move', string="Journal Entry")

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
        for line in dd.direct_deposit_line_ids:
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
            "status": "success",
            "id": dd.id
        }
    
    def _create_invoice(self):
        self.ensure_one()

        journal = self.env['account.journal'].search([('name', '=', 'Bank')], limit=1)

        move_vals = {
            "move_type": "entry",
            "date": fields.Date.today(),
            "ref": self.name,
            "journal_id": journal.id,
            "line_ids": [],
        }

        line_vals = []

        total_amount = 0.0

        for line in self.direct_deposit_line_ids:

            # CREDIT LINE (One per product line)
            credit_account = (
                line.product_id.property_account_income_id
                or line.product_id.categ_id.property_account_income_categ_id
            )
            if not credit_account:
                raise ValidationError(_("Missing credit account for product %s") % line.product_id.name)

            credit_line = (0, 0, {
                "name": credit_account.name,
                "account_id": credit_account.id,
                "credit": line.amount,
                "debit": 0,
                "company_id": self.env.company.id,
                "date_maturity": fields.Date.today(),
            })
            line_vals.append(credit_line)

            total_amount += line.amount

        # NOW ADD ONLY ONE DEBIT LINE
        receivable_account = self.env['account.account'].search([
            ('code', '=', '102401001'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        if not receivable_account:
            raise ValidationError(_("Missing debit account for the direct deposit."))

        debit_line = (0, 0, {
            "name": receivable_account.name,
            "account_id": receivable_account.id,
            "debit": total_amount,
            "credit": 0,
            "company_id": self.env.company.id,
            "date_maturity": fields.Date.today(),
        })
        line_vals.append(debit_line)

        move_vals["line_ids"] = line_vals

        move = self.env["account.move"].create(move_vals)

        # journal entry is parked (not posted)
        move.action_post()  # uncomment if you want posting

        self.move_id = move.id


    def action_clear(self):
        self._create_invoice()

        self.state = 'clear'

    def action_not_clear(self):
        self.state = 'not_clear'

    def action_show_invoice(self):
        return {
            "name": _("Invoice"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.move_id.id,
        }