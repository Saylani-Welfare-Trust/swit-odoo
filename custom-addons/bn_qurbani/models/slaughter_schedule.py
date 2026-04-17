from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SlaughterSchedule(models.Model):
    _name = 'slaughter.schedule'
    _description = 'Slaughter Schedule'


    name = fields.Char('Name', compute="_compute_name", default="New", store=True)

    day_id = fields.Many2one('qurbani.day', string="Day")
    hijri_id = fields.Many2one('hijri', string="Hijri")
    city_schedule_id = fields.Many2one('city.schedule', string="City Schedule", tracking=True)
    location_id = fields.Many2one('stock.location', string='Slaughter Location', tracking=True)
    demand = fields.Integer('Demand', tracking=True)

    slaughter_location_ids = fields.Many2many('stock.location', string="Slaughter Locations", compute="_set_slaughter_location_ids")

    location_ids = fields.Many2many('stock.location', string="Distribution Locations", tracking=True)

    start_time = fields.Float('Start Time', tracking=True)
    end_time = fields.Float('End Time', tracking=True)


    @api.depends('location_id')
    def _compute_name(self):
        for rec in self:
            if rec.location_id:
                rec.name = f"{rec.day_id.name} - {rec.hijri_id.name} - {rec.location_id.name} - {rec.start_time} to {rec.end_time}"

    @api.onchange('demand')
    def _onchange_demand(self):
        for rec in self:
            if rec.city_schedule_id:
                if rec.demand <= rec.city_schedule_id.remaining:
                    rec.city_schedule_id.remaining -= rec.demand
                else:
                    raise ValidationError(_('Demand cannot be greater than the remaining demand of the city schedule.'))

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
    

    @api.depends('city_schedule_id', 'city_schedule_id.location_ids')
    def _set_slaughter_location_ids(self):
        for record in self:
            if record.city_schedule_id:
                record.slaughter_location_ids = record.city_schedule_id.location_ids
            else:
                record.slaughter_location_ids = False