from odoo import models, fields, api

class ReturnMfdProduct(models.TransientModel):
    _name = 'return.mfd.product'

    product_id = fields.Many2one('product.product', string='Product')
    product_ids_domain = fields.Many2many('product.product', string='Product Domain')
    location_id = fields.Many2one('stock.location', 'Destination Location')
    remarks = fields.Html(string='Remarks')

    loan_id = fields.Many2one('mfd.loan.request')
    source_document = fields.Char()
    partner_id = fields.Many2one('res.partner')
    recovery_id = fields.Many2one('mfd.recovery', 'Recovery ID')

    def recovery_done(self):
        stock_move = self.env['stock.move'].create({
            'name': f'Recovered Product of Loan {self.source_document}',
            'product_id': self.product_id.id,
            'product_uom': self.product_id.uom_id.id,
            'product_uom_qty': 1,  # Decrease 1 unit
            'location_id': self.env.ref('stock.stock_location_customers').id,
            'location_dest_id': self.location_id.id,
            'state': 'draft',
        })
        picking = self.env['stock.picking'].create({
            'partner_id': self.partner_id.id,  # Link to customer
            'picking_type_id': self.env.ref('stock.picking_type_in').id,  # Outgoing picking type
            'move_ids_without_package': [(6, 0, [stock_move.id])],  # Associate the stock move with the picking
            'origin': self.source_document
        })
        stock_move._action_confirm()
        stock_move._action_assign()
        picking.action_confirm()
        picking.button_validate()


        self.recovery_id.write({
            'recovered_product_id': self.product_id.id,
            'recovered_location_id': self.location_id.id,
            'remarks': self.remarks,
            'state': 'recovered'
        })
        self.loan_id.write({
            'state': 'recovered',
        })









