from odoo import models, fields, api, _


class CitySchedule(models.Model):
    _name = 'city.schedule'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = 'City Schedule'


    day_id = fields.Many2one('qurbani.day', string="Day", tracking=True)
    hijri_id = fields.Many2one('hijri', string="Hijri", tracking=True)
    location_id = fields.Many2one('stock.location', string='City', tracking=True)
    inventory_product_id = fields.Many2one('product.product', string="Inventory Product", tracking=True)

    name = fields.Char('Name', default="New")
    inventory_product_name = fields.Char(related='inventory_product_id.name', string="Inentory Product Name")

    slaughter_location_id = fields.Many2one('stock.location', string='Slaughter Location', tracking=True)

    distribution_location_ids = fields.Many2many('stock.location', string="Distribution Locations", tracking=True)
    pos_product_ids = fields.Many2many('product.product', string="POS Products", tracking=True)


    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            day = None
            hijri = None
            location = None

            if vals.get('day_id'):
                day = self.env['qurbani.day'].browse(vals['day_id']).name
            if vals.get('hijri_id'):
                hijri = self.env['hijri'].browse(vals['hijri_id']).name
            if vals.get('location_id'):
                location = self.env['stock.location'].browse(vals['location_id']).name
            if vals.get('inventory_product_id'):
                inventory_product = self.env['product.product'].browse(vals['inventory_product_id']).name
            if vals.get('slaughter_location_id'):
                slaughter_location = self.env['stock.location'].browse(vals['slaughter_location_id']).name

            vals['name'] = f"{day or ''} - {hijri or ''} - {location or ''} - {inventory_product or ''} - {slaughter_location or ''}"

        return super(CitySchedule, self).create(vals)