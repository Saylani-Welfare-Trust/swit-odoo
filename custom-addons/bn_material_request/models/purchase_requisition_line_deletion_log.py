# -*- coding: utf-8 -*-

from odoo import models, fields


class PurchaseRequisitionLineDeletionLog(models.Model):
    """One row per deleted Purchase Request line: who deleted it, when, and
    what it was. Written by PurchaseRequisitionLine.unlink() just before the
    line itself is gone, so this is the only place that information survives.
    Nothing here is ever edited or removed through the UI - it is a log."""
    _name = 'purchase.requisition.line.deletion.log'
    _description = 'Purchase Request Line Deletion Log'
    _order = 'deleted_date desc, id desc'
    _rec_name = 'product_id'

    requisition_id = fields.Many2one(
        'purchase.requisition', string='Purchase Request', readonly=True, index=True,
        help='The Purchase Request the deleted line belonged to.')
    requisition_name = fields.Char(string='Purchase Request Ref.', readonly=True,
                                    help='Kept as plain text too, in case the Purchase Request '
                                         'itself is later deleted along with this line.')
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    product_uom_id = fields.Many2one('uom.uom', string='UoM', readonly=True)
    quantity = fields.Float(string='Requested Qty', readonly=True,
                             help='product_qty on the line at the moment it was deleted.')
    locked_qty = fields.Float(string='Locked Qty', readonly=True,
                               help='How much of the line had already gone out on a '
                                    'consolidated RFQ at the moment it was deleted.')
    description = fields.Text(string='Description', readonly=True)
    deleted_by = fields.Many2one('res.users', string='Deleted By', readonly=True, required=True, index=True)
    deleted_date = fields.Datetime(string='Deleted On', readonly=True, required=True, index=True,
                                    default=fields.Datetime.now)
