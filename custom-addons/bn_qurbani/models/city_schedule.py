from odoo import models, fields, api, _


class CitySchedule(models.Model):
    _name = 'city.schedule'
    _description = 'City Schedule'


    name = fields.Char('Name', default="New")

    day_id = fields.Many2one('qurbani.day', string="Day", tracking=True)
    hijri_id = fields.Many2one('hijri', string="Hijri", tracking=True)
    location_id = fields.Many2one('stock.location', string='City', tracking=True)
    
    demand = fields.Integer('Demand', tracking=True)
    remaining = fields.Integer('Remaining', compute="_set_remaining", store=True, tracking=True)

    location_ids = fields.Many2many('stock.location', string='Slaughter Locations', tracking=True)


    @api.depends('demand')
    def _set_remaining(self):
        for rec in self:
            if rec.demand:
                rec.remaining = rec.demand - rec.remaining

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

            vals['name'] = f"{day or ''} - {hijri or ''} - {location or ''}"

        return super(CitySchedule, self).create(vals)