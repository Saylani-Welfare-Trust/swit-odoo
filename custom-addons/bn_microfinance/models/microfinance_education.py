from odoo import models, fields


examination_selection = [
    ('matric', 'Matric'),
    ('inter', 'Inter'),
    ('under_graduate', 'Under Graduate'),
    ('graduate', 'Graduate'),
    ('post_grduate', 'Post Graduate'),
    ('master', 'Master'),
]


class MicrofinanceEducaiton(models.Model):
    _name = 'microfinance.education'
    _description = "Microfinance Educaiton"


    microfinance_id = fields.Many2one('microfinance', string="Microfinance")

    board = fields.Char('Board')
    passing_year = fields.Char('Passing Year')
    school_uni_center = fields.Char('School/Uni/Center')

    examination = fields.Selection(selection=examination_selection, string="Examination")

    percentage = fields.Float('Percentage')