from odoo import models, fields, api, _


class QurbaniGoatDistribution(models.Model):
    _name = 'qurbani.goat.distribution'
    _description = "Qurbani Goat Distribution"


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

    qurbani_goat_distribution_line = fields.One2many('qurbani.goat.distribution.line', 'qurbani_goat_distribution_id', string="Qurbani Goat Distribution Line")

    product_id = fields.Many2one('product.product', string="Product")

    qurbani_order_no = fields.Char('QO No.')
    qurbani_order_line_no = fields.Char('QOL No.')
    hissa_name = fields.Char('Hissa Name')


    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('qurbani_goat_distribution') or ('New')

        return super(QurbaniGoatDistribution, self).create(vals)