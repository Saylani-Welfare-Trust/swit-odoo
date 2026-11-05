# -*- coding: utf-8 -*-
from odoo import api, fields, models


class BnSourceDocumentMixin(models.AbstractModel):
    """The program record (Welfare, Direct Deposit, Qurbani ...) a transfer or
    journal entry was made for, so it can be opened from there."""
    _name = 'bn.source.document.mixin'
    _description = 'Source program document'

    bn_source_ref = fields.Reference(
        selection='_bn_source_models', string='Source Record', readonly=True, copy=False, index=True)

    @api.model
    def _bn_source_models(self):
        return [(model.model, model.name) for model in self.env['ir.model'].sudo().search(
            [('model', 'not like', 'ir.%'), ('transient', '=', False)])]

    def action_open_bn_source(self):
        self.ensure_one()
        record = self.bn_source_ref
        if not record:
            return False
        return {'type': 'ir.actions.act_window', 'res_model': record._name, 'res_id': record.id,
                'view_mode': 'form', 'target': 'current'}

    @api.model
    def _bn_source_vals(self, record):
        """Values linking a new transfer / entry to ``record``."""
        record = record[:1]
        return {'bn_source_ref': '%s,%s' % (record._name, record.id)} if record else {}


class StockPicking(models.Model):
    _name = 'stock.picking'
    _inherit = ['stock.picking', 'bn.source.document.mixin']


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'bn.source.document.mixin']
