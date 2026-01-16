from odoo import models, fields,api


state_selection = [
    ('draft', 'Draft'),
    ('delivered', 'Delivered'),
    ('disbursed', 'Disbursed'),
]

collection_point_selection = [
    ('bank', 'Bank'),
    ('branch', 'Branch'),
]


class WelfareRecurringLine(models.Model):
    _name = 'welfare.recurring.line'
    _description = "Welfare Recurring Line"


    welfare_id = fields.Many2one('welfare', string="Welfare")
    name = fields.Char('Name', compute='_compute_name', store=True)
        
    donee_id = fields.Many2one('res.partner', string="Donee", related='welfare_id.donee_id', store=True)
    product_id = fields.Many2one('product.product', string="Product")
    analytic_account_id = fields.Many2one('account.analytic.account', string="Branch")
    disbursement_category_id = fields.Many2one('disbursement.category', string="Disbursement Category")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)
    disbursement_application_type_id = fields.Many2one('disbursement.application.type', string="Disbursement Application Type")

    collection_point = fields.Selection(selection=collection_point_selection, string="Collection Point")

    collection_date = fields.Date('Collection Date', default=fields.Date.today())

    amount = fields.Monetary('Amount', currency_field='currency_id')
    quantity = fields.Float('Quantity', default=1.0)
    state = fields.Selection(selection=state_selection, string="Order Type")
    
    @api.depends('welfare_id')
    def _compute_name(self):
            for rec in self:
                rec.name = rec.welfare_id.name if rec.welfare_id else ''
    
    def action_delivered(self):
            in_kind_category = self.env.ref('bn_master_setup.disbursement_category_in_kind')
            if self.disbursement_category_id == in_kind_category:        
                StockPicking = self.env['stock.picking']
                StockMove = self.env['stock.move']
                StockMoveLine = self.env['stock.move.line']
                # You may want to adjust picking_type_id, location_id, location_dest_id as per your setup
                location_src = self.env['stock.location'].search([('usage', '=', 'internal')], limit=1)
                location_dest = self.env['stock.location'].search([('usage', '=', 'customer')], limit=1)
                picking_vals = {
                    'partner_id': self.donee_id.id,
                    'picking_type_id': self.env.ref('stock.picking_type_out').id,
                    'location_id': location_src.id if location_src else False,
                    'location_dest_id': location_dest.id if location_dest else False,
                    'origin': self.name,
                }
                picking = StockPicking.create(picking_vals)
                move_vals = {
                    'name': self.product_id.display_name,
                    'product_id': self.product_id.id,
                    'product_uom_qty': self.quantity,
                    'product_uom': self.product_id.uom_id.id,
                    'picking_id': picking.id,
                    'location_id': location_src.id if location_src else False,
                    'location_dest_id': location_dest.id if location_dest else False,
                }
                move = StockMove.create(move_vals)
                move_line_vals = {
                    'move_id': move.id,
                    'product_id': self.product_id.id,
                    'product_uom_id': self.product_id.uom_id.id,
                    'quantity': self.quantity,
                    'picking_id': picking.id,
                    'location_id': location_src.id if location_src else False,
                    'location_dest_id': location_dest.id if location_dest else False,
                    'recurring_line_id': self.id,
                }
                StockMoveLine.create(move_line_vals)
                self.state = 'delivered'