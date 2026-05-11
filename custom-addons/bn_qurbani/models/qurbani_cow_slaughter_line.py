from odoo import models, fields


option_selection = [
    ('no', 'No'),
    ('yes', 'Yes'),
]


class QurbaniCowSlaughterLine(models.Model):
    _name = 'qurbani.cow.slaughter.line'
    _description = "Qurbani Cow Slaughter Line"


    qurbani_cow_slaughter_id = fields.Many2one('qurbani.cow.slaughter', string="Qurbani Cow Slaughter")

    qurbani_order_no = fields.Char('QO No.')
    qurbani_order_line_no = fields.Char('QOL No.')
    hissa_name = fields.Char('Hissa Name')

    option = fields.Selection(selection=option_selection, string="Option")