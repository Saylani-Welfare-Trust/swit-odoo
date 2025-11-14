from odoo import models, fields


class ReturnMicrofinanceProduct(models.TransientModel):
    _name = 'return.microfinance.product'
    _description = "Return Microfinance Product"


    donee_id = fields.Many2one('res.partner', string="Donee")
    product_id = fields.Many2one('product.product', string='Product')
    microfinance_id = fields.Many2one('microfinance', string="Microfinance")
    destination_location_id = fields.Many2one('stock.location', string="Destination Location")

    product_domain = fields.Many2many('product.product', string='Product Domain')

    remarks = fields.Text('Remarks')
    source_document = fields.Char('Source Document')

    def action_recovery_done(self):
        stock_move = self.env['stock.move'].create({
            'name': f'Recovered Product of Loan {self.source_document}',
            'product_id': self.product_id.id,
            'product_uom': self.product_id.uom_id.id,
            'product_uom_qty': 1,  # Decrease 1 unit
            'location_id': self.env.ref('stock.stock_location_customers').id,
            'location_dest_id': self.destination_location_id.id
        })

        picking = self.env['stock.picking'].create({
            'partner_id': self.donee_id.id,
            'picking_type_id': self.env.ref('stock.picking_type_in').id,
            'move_ids_without_package': [(6, 0, [stock_move.id])],
            'origin': self.source_document
        })
        
        picking.action_confirm()
        picking.action_assign()
        picking.button_validate()


        self.microfinance_id.write({
            'recovered_location_id': self.destination_location_id.id,
            'recovery_remarks': self.remarks,
            'state': 'recover'
        })