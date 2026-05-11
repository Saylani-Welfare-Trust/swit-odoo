from odoo import models, fields, api, _


class QurbaniGoatDistribution(models.Model):
    _name = 'qurbani.cow.distribution'
    _description = "Qurbani Cow Distribution"


    hijri_id = fields.Many2one('hijri', string="Hijri")
    day_id = fields.Many2one('qurbani.day', string="Day")
    distribution_location_id = fields.Many2one('stock.location', string="Distribution Location")

    start_time = fields.Float('Start Time')
    end_time = fields.Float('End Time')

    video = fields.Binary('Video')
    image = fields.Binary('Image')

    name = fields.Char('Name')
    video_file_name = fields.Char('Video File Name')
    image_file_name = fields.Char('Image File Name')

    qurbani_goat_distribution_line = fields.One2many('qurbani.goat.distribution.line', 'qurbani_goat_distribution_id', string="Qurbani Goat Distribution Line")


    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('qurbani_goat_distribution') or ('New')

        return super(QurbaniGoatDistribution, self).create(vals)