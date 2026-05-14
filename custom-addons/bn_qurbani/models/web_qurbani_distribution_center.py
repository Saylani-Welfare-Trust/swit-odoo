from odoo import models, fields, api

class QurbaniDistributionCenter(models.Model):
    _name = 'web.qurbani.distribution.center'
    _description = "Qurbani Distribution Center"


    name = fields.Char('Name')  
    distribution_center_id = fields.Many2one('stock.location', string="Distribution Center")