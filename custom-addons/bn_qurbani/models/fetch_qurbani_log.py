from odoo import models, fields


class FetchLog(models.Model):
    _name = 'fetch.qurbani.log'
    _description = "Fetch Log"


    name = fields.Text('Name')
    
    status = fields.Char('Status')
    reason = fields.Char('Reason')
    
