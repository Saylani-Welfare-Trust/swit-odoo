# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.tools.sql import column_exists, rename_column


class SourceDocumentMixin(models.AbstractModel):
    """The program record (Welfare, Direct Deposit, Qurbani ...) a transfer or
    journal entry was made for, so it can be opened from there."""
    _name = 'source.document.mixin'
    _description = 'Source program document'

    source_record_ref = fields.Reference(
        selection='_source_models', string='Source Record', readonly=True, copy=False, index=True)

    def _auto_init(self):
        # the column of an earlier version keeps its links
        if column_exists(self.env.cr, self._table, 'bn_source_ref') \
                and not column_exists(self.env.cr, self._table, 'source_record_ref'):
            rename_column(self.env.cr, self._table, 'bn_source_ref', 'source_record_ref')
        return super()._auto_init()

    @api.model
    def _source_models(self):
        return [(model.model, model.name) for model in self.env['ir.model'].sudo().search(
            [('model', 'not like', 'ir.%'), ('transient', '=', False)])]


class StockPicking(models.Model):
    _name = 'stock.picking'
    _inherit = ['stock.picking', 'source.document.mixin']


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'source.document.mixin']
