from odoo import models, fields


class KeyIssuance(models.Model):
    _inherit = 'key.issuance'


    rider_collection_id = fields.Many2one('rider.collection', string="Rider Collection")