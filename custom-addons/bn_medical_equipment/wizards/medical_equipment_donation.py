from odoo import models, fields, _
from odoo.exceptions import ValidationError


class MedicalEquipmentDonation(models.TransientModel):
    _name = 'medical.equipment.donation'
    _description = "Medical Equipment Donation"


    medical_equipment_id = fields.Many2one('medical.equipment', string="Medical Equipment")
    product_id = fields.Many2one('product.product', string="Product")


    def action_confirm(self):
        self.ensure_one()

        if not self.medical_equipment_line_ids:
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

        line_vals = []
        total_amount = 0.0

        for line in self.medical_equipment_id.medical_equipment_line_ids:
            product = line.product_id
            amount = line.security_deposit * line.quantity

            if not amount:
                continue

            income_account = (
                product.property_account_income_id
                or product.categ_id.property_account_income_categ_id
            )
            expense_account = (
                security_product.property_account_expense_id
                or security_product.categ_id.property_account_expense_categ_id
            )

            if not income_account or not expense_account:
                raise ValidationError(
                    _(f"Income or Expense account missing for product {product.display_name}")
                )

            # Debit → Expense
            line_vals.append((0, 0, {
                'name': f"Donation Expense - {product.name}",
                'account_id': expense_account.id,
                'debit': amount,
                'credit': 0.0,
            }))

            # Credit → Income
            line_vals.append((0, 0, {
                'name': f"Donation Income - {product.name}",
                'account_id': income_account.id,
                'debit': 0.0,
                'credit': amount,
            }))

            total_amount += amount

        if not line_vals:
            raise ValidationError(_("Nothing to post for donation."))

        move_vals = {
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': fields.Date.today(),
            'ref': f"Medical Equipment Donation - {self.name}",
            'line_ids': line_vals,
        }

        move = self.env['account.move'].create(move_vals)
        # DO NOT POST → parked entry

        self.medical_equipment_id.state = 'donate'
        self.medical_equipment_id.state = move.id