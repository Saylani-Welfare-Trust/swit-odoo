from odoo import models, fields


class PlanningType(models.Model):
    _name = 'planning.type'
    _description = 'Planning Type'
    _rec_name = 'name'

    name = fields.Char(string='Name', required=True)

    kitchen   = fields.Boolean(string='Kitchen Planning')
    madaris   = fields.Boolean(string='Madaris Planning')
    medical   = fields.Boolean(string='Medical Planning')
    livestock = fields.Boolean(string='Livestock Planning')
    food      = fields.Boolean(string='Food Planning')
    ration    = fields.Boolean(string='Ration Planning')
    meat      = fields.Boolean(string='Meat Planning')