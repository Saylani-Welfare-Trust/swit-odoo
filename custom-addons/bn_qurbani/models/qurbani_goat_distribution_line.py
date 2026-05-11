from odoo import models, fields


option_selection = [
    ('no', 'No'),
    ('yes', 'Yes'),
]


class QurbaniGoatDistributionLine(models.Model):
    _name = 'qurbani.goat.distribution.line'
    _description = "Qurbani Goat Distribution Line"


    qurbani_goat_distribution_id = fields.Many2one('qurbani.goat.distribution', string="Qurbani Goat Distribution")

    qurbani_order_no = fields.Char('QO No.')
    qurbani_order_line_no = fields.Char('QOL No.')
    hissa_name = fields.Char('Hissa Name')

    option = fields.Selection(selection=option_selection, string="Option")