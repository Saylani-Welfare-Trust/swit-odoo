from odoo import models, fields, api, _


class QurbaniGoatSlaughter(models.Model):
    _name = 'qurbani.goat.slaughter'
    _description = "Qurbani Goat Slaughter"


    hijri_id = fields.Many2one('hijri', string="Hijri")
    day_id = fields.Many2one('qurbani.day', string="Day")
    slaughter_location_id = fields.Many2one('stock.location', string="Slaughter Location")

    start_time = fields.Float('Start Time')
    end_time = fields.Float('End Time')

    video = fields.Binary('Video')
    image = fields.Binary('Image')

    name = fields.Char('Name')
    video_file_name = fields.Char('Video File Name')
    image_file_name = fields.Char('Image File Name')

    slot_full = fields.Interger('Slot Full', compute="_set_slot_full", store=True)

    qurbani_goat_slaughter_line = fields.One2many('qurbani.goat.slaughter.line', 'qurbani_goat_slaughter_id', string="Qurbani Cow Slaughter Line")


    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('qurbani_goat_slaughter') or ('New')

        return super(QurbaniGoatSlaughter, self).create(vals)
    
    @api.depends('qurbani_goat_distribution_line')
    def _set_slot_full(self):
        for rec in self:
            rec.slot_full = len(rec.qurbani_goat_distribution_line)