from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class LoanProductInstallment(models.Model):
    _name = 'loan.product.installment'
    _description = "Loan Product Installment"
    _rec_name = 'no_of_installment'
    _order = 'no_of_installment'


    loan_product_line_id = fields.Many2one('loan.product.line', string='Loan Product Line', ondelete='cascade')

    no_of_installment = fields.Integer('No. of Installments')

    _sql_constraints = [
        ('unique_installment_per_product_line', 'unique(loan_product_line_id, no_of_installment)', 'This No. of Installments is already added for this product.'),
    ]

    @api.constrains('no_of_installment')
    def _check_no_of_installment(self):
        for rec in self:
            if rec.no_of_installment <= 0:
                raise ValidationError('No. of Installments must be greater than zero.')

    @api.model
    def name_create(self, name):
        # Options are typed in as tags, so the typed text has to be a number.
        # UserError on purpose: a ValidationError makes the tags widget open a create form instead of showing the message
        name = (name or '').strip()

        if not name.isdecimal() or int(name) <= 0:
            raise UserError('No. of Installments must be a whole number greater than zero.')

        return super(LoanProductInstallment, self).name_create(name)
