from odoo import models, fields


option_selection = [
    ('no', 'No'),
    ('yes', 'Yes'),
]


class QurbaniCowDistributionLine(models.Model):
    _name = 'qurbani.cow.distribution.line'
    _description = "Qurbani Cow Distribution Line"


    qurbani_cow_distribution_id = fields.Many2one('qurbani.cow.distribution', string="Qurbani Cow Distribution")

    qurbani_order_no = fields.Char('QO No.')
    qurbani_order_line_no = fields.Char('QOL No.')
    hissa_name = fields.Char('Hissa Name')

    option = fields.Selection(selection=option_selection, string="Option")