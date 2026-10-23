from odoo import models, fields

class QurbaniCity(models.Model):
    _name = 'qurbani.city'
    _description = 'Qurbani City'

    name = fields.Char('Web Qurbani City')
    city_id = fields.Many2one('stock.location', string="City")
