from odoo import models, fields


class ChandRaat(models.Model):
    _name = 'chand.raat'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = 'Chand Raat'

    
    date_time = fields.Datetime('Date Time', tracking=True)