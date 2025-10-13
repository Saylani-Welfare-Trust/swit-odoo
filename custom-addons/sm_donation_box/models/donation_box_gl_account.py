from odoo import fields, models, api


class DonationBoxGLAccount(models.Model):
    _name = 'donation.box.gl.account'
    _descripiton = "Donation Box GL Account"


    product_id = fields.Many2one('product.product', string="Product ID")
    account_id = fields.Many2one('account.account', string='GL Account')

    name = fields.Char('Name', compute="_set_name", store=True)


    @api.depends('product_id')
    def _set_name(self):
        for rec in self:
            rec.name = rec.product_id.name