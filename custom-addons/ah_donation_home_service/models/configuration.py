from odoo import fields,api,models

class DhsAccountConfiguration(models.Model):
    _name = 'dhs.account.configuration'

    name = fields.Char(string='Name')
    account_id = fields.Many2one('account.account', 'Chart of Account')


class ProductConfiguration(models.Model):
    _name = 'dhs.product.conf'

    product_id = fields.Many2one('product.product', 'Product')
    return_product_id = fields.Many2one('product.product', 'Return Product')
    @api.model
    def get_dhs_products(self):
        records = self.search([]).filtered(lambda r: r.product_id)
        return [r.product_id.id for r in records]