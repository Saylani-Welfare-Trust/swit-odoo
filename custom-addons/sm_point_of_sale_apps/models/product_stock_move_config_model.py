from odoo import api, fields, models, _


class ProductStockMoveConfigModel(models.Model):
    _name = 'product.stock.move.config'
    _description = 'Product Stock Move Config Model'
    _rec_name = 'location_id'

    def default_set_value(self, name):
        stock_picking_type = self.env['stock.picking.type'].sudo().search([('code', '=', 'incoming')], limit=1)
        if stock_picking_type:
            field_map = {
                'stock_picking_type_id': stock_picking_type.id,
            }
            return field_map.get(name, False)
        return False

    location_id = fields.Many2one(comodel_name='stock.location', string='Location', required=True, domain="[('usage', '=', 'internal')]")
    stock_picking_type_id = fields.Many2one(comodel_name='stock.picking.type', string='Operations Types', domain="[('code', '=', 'incoming')]", default=lambda self: self.default_set_value('stock_picking_type_id'))
    debit_account_id = fields.Many2one(comodel_name='account.account', string='Account (Dr)', required=True, domain="[('account_type', 'in', ['asset_receivable', 'asset_cash', 'asset_current', 'asset_non_current', 'asset_prepayments', 'asset_fixed'])]")
    credit_account_id = fields.Many2one(comodel_name='account.account', string='Account (Cr)', required=True, domain="[('account_type', 'in', ['income', 'income_other'])]")
    journal_id = fields.Many2one(comodel_name='account.journal', string='Journal', required=True, domain="[('type', '=', 'sale')]")
    company_id = fields.Many2one(comodel_name='res.company', string='Company', default=lambda self: self.env.company)

