from odoo import api, fields, models




class RequisitionOrder(models.Model):
    _inherit = 'requisition.order'

    is_epr  = fields.Boolean(
        related='product_id.is_epr',

        required=False)