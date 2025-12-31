from odoo import models, fields


class DonationHomeServiceLine(models.Model):
    _name = 'donation.home.service.line'
    _description = "Donation Home Servcie Line"


    donation_home_service_id = fields.Many2one('donation.home.service', string="Donation Home Service")
    product_id = fields.Many2one('product.product', string="Product")
    currency_id = fields.Many2one('res.currency', related='donation_home_service_id.currency_id')
    
    quantity = fields.Integer('Quantity', default=1)

    amount = fields.Monetary('Amount', currency_field='currency_id')

    remarks = fields.Char('Remarks')