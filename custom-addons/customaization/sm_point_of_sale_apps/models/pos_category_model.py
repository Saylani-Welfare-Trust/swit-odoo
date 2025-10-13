from odoo import api, fields, models, _

type_selection = [
    ('default', 'Default'),
    ('box', 'Box'),
    ('box_open', 'Box Open')
]

level_selection = [
    ('level_0', 'level 0'),
    ('level_1', 'level 1'),
    ('level_2', 'level 2'),
    ('level_3', 'level 3'),
    ('level_4', 'level 4'),
    ('level_5', 'level 5'),
]

class POSCategoryModelInherit(models.Model):
    _inherit = 'pos.category'

    type = fields.Selection(selection=type_selection, string='Type', default='default', required=True)
    level = fields.Selection(selection=level_selection, string='Level', default='level_0', required=True)

