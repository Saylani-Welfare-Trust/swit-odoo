from odoo import models, fields


class Area(models.Model):
    _name = 'area'
    _description = "Area"


    name = fields.Char('Name')
    area_code = fields.Char('Area Code')
    
    area_description = fields.Text('Area Description')
    
    active_status = fields.Boolean('Active Status', default=True)