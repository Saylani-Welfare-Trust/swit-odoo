from odoo import fields, models, api, exceptions


class DisbursementCategory(models.Model):
    _name = 'disbursement.category'
    _description = 'Disbursement Category'
    _inherit = ["mail.thread", "mail.activity.mixin"]


    name = fields.Char('Name', tracking=True)