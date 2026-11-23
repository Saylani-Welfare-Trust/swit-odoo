from odoo import models, fields, api


class Bank(models.Model):
    _name = 'bank'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Bank"


    name = fields.Char('Name')


    @api.model
    def get_banks(self):
        return [{'id': bank.id, 'name': bank.name} for bank in self.search([])]