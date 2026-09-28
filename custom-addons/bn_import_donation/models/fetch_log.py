from odoo import models, fields


class FetchLog(models.Model):
    _name = 'fetch.log'
    _description = "Fetch Log"


    name = fields.Text('Name')
    
    status = fields.Char('Status')
    reason = fields.Char('Reason')
    
    fetch_history_id = fields.Many2one('fetch.history', string="Fetch History")