from odoo import models, fields


class ChandRaat(models.Model):
    _name = 'chand.raat'
    _description = 'Chand Raat'

    
    date_time = fields.Datetime('Date Time')