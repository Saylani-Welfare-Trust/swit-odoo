from odoo import models, fields


class MedicalEquipmentCategory(models.Model):
    _name = 'medical.equipment.category'
    _description = "Medical Equipment Category"


    name = fields.Char('Name')

    product_id = fields.Many2one('product.product', string="Product")
    currency_id = fields.Many2one('res.currency', string="Currency", default=lambda self: self.env.company.currency_id)

    is_medical_approval = fields.Boolean('Is Medical Approval')

    security_deposit = fields.Monetary('Security Deposit', currency_field='currency_id')

    # recovery_period = fields.Integer('Recovery Period')