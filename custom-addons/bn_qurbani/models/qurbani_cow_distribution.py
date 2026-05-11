from odoo import models, fields, api, _


class QurbaniCowDistribution(models.Model):
    _name = 'qurbani.cow.distribution'
    _description = "Qurbani Cow Distribution"


    hijri_id = fields.Many2one('hijri', string="Hijri")
    day_id = fields.Many2one('qurbani.day', string="Day")
    inventory_product_id = fields.Many2one('product.product', string="Inventory Product")
    distribution_location_id = fields.Many2one('stock.location', string="Distribution Location")

    start_time = fields.Float('Start Time')
    end_time = fields.Float('End Time')

    video = fields.Binary('Video')
    image = fields.Binary('Image')

    name = fields.Char('Name')
    video_file_name = fields.Char('Video File Name')
    image_file_name = fields.Char('Image File Name')

    product_id = fields.Many2one('product.product', string="Product")

    qurbani_order_no = fields.Char('QO No.')
    qurbani_order_line_no = fields.Char('QOL No.')
    hissa_name = fields.Char('Hissa Name')


    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('qurbani_cow_distribution') or ('New')

        return super(QurbaniCowDistribution, self).create(vals)