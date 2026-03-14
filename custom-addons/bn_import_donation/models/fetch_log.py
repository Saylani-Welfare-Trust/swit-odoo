from odoo import models, fields


class FetchLog(models.Model):
    _name = 'fetch.log'
    _description = "Fetch Log"


    name = fields.Text(string="Name")
    
    fetch_history_id = fields.Many2one('fetch.history', string="Fetch History")