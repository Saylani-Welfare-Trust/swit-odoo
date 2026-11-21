from odoo import models, fields, _
from odoo.exceptions import ValidationError


class MedicalEquipmentDonation(models.TransientModel):
    _name = 'medical.equipment.donation'
    _description = "Medical Equipment Donation"


    medical_equipment_id = fields.Many2one('medical.equipment', string="Medical Equipment")
    product_id = fields.Many2one('product.product', string="Product")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id.id)

    remarks = fields.Text('Remarks')

    amount = fields.Monetary('Amount', currency_field='currency_id')


    def action_confirm(self):
        self.ensure_one()

        if not self.medical_equipment_id.medical_equipment_line_ids:
            raise ValidationError(_("No medical equipment lines found."))

        journal = self.env['account.journal'].search(
            [('type', '=', 'general'), ('company_id', '=', self.env.company.id)],
            limit=1
        )
        
        security_product = self.env['product.product'].search(
            [('name', '=', self.env.company.medical_equipment_security_depsoit_product)],
            limit=1
        )

        if not journal:
            raise ValidationError(_("Please configure a General Journal."))

        income_account = (
            self.product_id.property_account_income_id
            or self.product_id.categ_id.property_account_income_categ_id
        )
        expense_account = (
            security_product.property_account_expense_id
            or security_product.categ_id.property_account_expense_categ_id
        )
        if not income_account or not expense_account:
            raise ValidationError(_(
                "Set an income account on %(product)s and an expense account on the security deposit product.",
                product=self.product_id.display_name or _('the donation product')))

        # the deposit of each equipment line; the amount of the wizard, when given,
        # is the part of the whole deposit that is donated: posted once, not per line
        deposits = [(line.product_id, line.security_deposit * line.quantity)
                    for line in self.medical_equipment_id.medical_equipment_line_ids
                    if line.security_deposit * line.quantity]
        total_deposit = sum(amount for _product, amount in deposits)
        if self.amount:
            if self.amount < 0 or self.currency_id.compare_amounts(self.amount, total_deposit) > 0:
                raise ValidationError(_(
                    "The donated amount must be positive and not more than the security deposit (%s).",
                    total_deposit))
            deposits = [(self.product_id or security_product, self.amount)]

        line_vals = []
        for product, amount in deposits:
            line_vals.append((0, 0, {
                'name': f"Donation Expense - {product.name}",
                'account_id': expense_account.id,
                'debit': amount,
                'credit': 0.0,
            }))
            line_vals.append((0, 0, {
                'name': f"Donation Income - {product.name}",
                'account_id': income_account.id,
                'debit': 0.0,
                'credit': amount,
            }))

        if not line_vals:
            raise ValidationError(_("Nothing to post for donation."))

        move_vals = {
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': fields.Date.today(),
            'ref': f"Medical Equipment Donation - {self.medical_equipment_id.name}",
            'line_ids': line_vals,
        }

        move = self.env['account.move'].with_context(default_source_record_ref='%s,%s' % (self.medical_equipment_id._name, self.medical_equipment_id.id)).create(move_vals)
        # DO NOT POST → parked entry

        self.medical_equipment_id.state = 'donate'
        self.medical_equipment_id.move_id = move.id
        self.medical_equipment_id.general_remarks = self.remarks
        self.medical_equipment_id.remaining_amount = self.medical_equipment_id.total_amount - self.amount if self.amount else 0.0