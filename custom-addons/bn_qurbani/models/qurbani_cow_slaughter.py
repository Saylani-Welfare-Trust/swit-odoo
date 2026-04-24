from odoo import models, fields


class QurbaniCowSlaughter(models.Model):
    _name = 'qurbani.cow.slaughter'
    _description = "Qurbani Cow Slaughter"


    hijri_id = fields.Many2one('hijri', string="Hijri")
    day_id = fields.Many2one('qurbani.day', string="Day")
    slaughter_location_id = fields.Many2one('stock.location', string="Slaughter Location")

    start_time = fields.Float('Start Time')
    end_time = fields.Float('End Time')

    qurbani_order_no = fields.Char('QO No.')
    qurbani_order_line_no = fields.Char('QOL No.')

    video = fields.Binary('Video')
    image = fields.Binary('Image')

    hissa_name = fields.Char('Hissa Name')
    video_file_name = fields.Char('Video File Name')
    image_file_name = fields.Char('Image File Name')