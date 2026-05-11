from odoo import models, fields


option_selection = [
    ('no', 'No'),
    ('yes', 'Yes'),
]


class QurbaniGoatSlaughterLine(models.Model):
    _name = 'qurbani.goat.slaughter.line'
    _description = "Qurbani Goat Slaughter Line"


    qurbani_goat_slaughter_id = fields.Many2one('qurbani.goat.slaughter', string="Qurbani Goat Slaughter")

    qurbani_order_no = fields.Char('QO No.')
    qurbani_order_line_no = fields.Char('QOL No.')
    hissa_name = fields.Char('Hissa Name')

    option = fields.Selection(selection=option_selection, string="Option")