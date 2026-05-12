from odoo import models, fields, api, _


class QurbaniCowDistribution(models.Model):
    _name = 'qurbani.cow.distribution'
    _description = "Qurbani Cow Distribution"


    hijri_id = fields.Many2one('hijri', string="Hijri")
    day_id = fields.Many2one('qurbani.day', string="Day")
    inventory_product_id = fields.Many2one('product.product', string="Inventory Product")
    slaughter_location_id = fields.Many2one('stock.location', string="Slaughter Location")

    start_time = fields.Float('Start Time')
    end_time = fields.Float('End Time')
    slaughter_start_time = fields.Float('Start Time')
    slaughter_end_time = fields.Float('End Time')

    name = fields.Char('Name')

    product_id = fields.Many2one('product.product', string="Product")

    qurbani_order_no = fields.Char('QO No.')
    qurbani_order_line_no = fields.Char('QOL No.')
    hissa_name = fields.Char('Hissa Name')


    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('qurbani_cow_distribution') or ('New')

        return super(QurbaniCowDistribution, self).create(vals)