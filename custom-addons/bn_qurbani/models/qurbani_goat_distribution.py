from odoo import models, fields, api, _


class QurbaniGoatDistribution(models.Model):
    _name = 'qurbani.goat.distribution'
    _description = "Qurbani Goat Distribution"


    hijri_id = fields.Many2one('hijri', string="Hijri")
    day_id = fields.Many2one('qurbani.day', string="Day")
    inventory_product_id = fields.Many2one('product.product', string="Inventory Product")
    distribution_location_id = fields.Many2one('stock.location', string="Distribution Location")
    slaughter_location_id = fields.Many2one('stock.location', string="Slaughter Location")

    start_time = fields.Float('Start Time')
    end_time = fields.Float('End Time')
    slaughter_start_time = fields.Float('Start Time')
    slaughter_end_time = fields.Float('End Time')

    name = fields.Char('Name', default="New")

    product_id = fields.Many2one('product.product', string="Product")

    qurbani_order_no = fields.Char('QO No.')
    qurbani_order_line_no = fields.Char('QOL No.')
    hissa_name = fields.Char('Hissa Name')


    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('qurbani_goat_distribution') or ('New')

        return super(QurbaniGoatDistribution, self).create(vals)