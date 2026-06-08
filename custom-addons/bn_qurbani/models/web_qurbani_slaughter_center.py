from odoo import models, fields, api

class QurbaniDistributionCenter(models.Model):
    _name = 'web.qurbani.slaughter.center'
    _description = "Qurbani Distribution Center"


    name = fields.Char('Name')  
    slaughter_center_id = fields.Many2one('stock.location', string="Slaughter Center" )
    distribution_center_id = fields.Many2many('stock.location', string="Distribution Center")
    
    

    
    
    