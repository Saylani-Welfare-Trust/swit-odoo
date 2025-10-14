from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    
    disbursement_type_ids = fields.Many2many('disbursement.type', string="Disbursement Type ID")
    
    welfare_ids = fields.One2many('disbursement.request', 'donee_id', string="Welfare IDs")

    city_id = fields.Many2one('res.city', string="City", tracking=True)

    cnic_expiration_date = fields.Date('CNIC Expiration Date', tracking=True)