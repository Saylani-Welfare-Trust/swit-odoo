from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SlaughterSchedule(models.Model):
    _name = 'slaughter.schedule'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = 'Slaughter Schedule'


    day_id = fields.Many2one('qurbani.day', string="Day", tracking=True)
    hijri_id = fields.Many2one('hijri', string="Hijri", tracking=True)
    city_location_id = fields.Many2one('stock.location', string="City Location", tracking=True)
    location_id = fields.Many2one('stock.location', string='Slaughter Location', tracking=True)
    inventory_product_id = fields.Many2one('product.product', string="Inventory Product", tracking=True)

    name = fields.Char('Name', compute="_compute_name", default="New", store=True)
    inventory_product_name = fields.Char(related='inventory_product_id.name', string="Inentory Product Name")

    start_time = fields.Float('Start Time', tracking=True)
    end_time = fields.Float('End Time', tracking=True)


    @api.depends('location_id')
    def _compute_name(self):
        for rec in self:
            if rec.location_id:
                rec.name = f"{rec.day_id.name} - {rec.hijri_id.name} - {rec.location_id.name} - {rec.start_time} to {rec.end_time}"

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

            vals['name'] = f"{day or ''} - {hijri or ''} - {location or ''} - {vals.get('start_time', '')} to {vals.get('end_time', '')}"

        return super(SlaughterSchedule, self).create(vals)