from odoo import fields, models, api, exceptions, _


state_selection = [
    ('draft', 'Draft'),
    ('disbursed', 'Disbursed'),
]


collection_point_selection = [
    ('bank', 'Bank'),
    ('branch', 'Branch'),
]



class RecurringDisbursementRequest(models.Model):
    _name = 'recurring.disbursement.request'
    _description = 'Reccurring Disbursement Request'


    disbursement_request_line_id = fields.Many2one('disbursement.request.line', string="Disbursement Request Line ID")

    disbursement_request_id = fields.Many2one(related='disbursement_request_line_id.disbursement_request_id', string="Disbursement Request ID", store=True)
    donee_id = fields.Many2one(related='disbursement_request_line_id.disbursement_request_id.donee_id', string="Donee ID", store=True)
    disbursement_category_id = fields.Many2one(related='disbursement_request_line_id.disbursement_category_id', string="Disbursement Catgeory ID", store=True)
    branch_id = fields.Many2one(related='disbursement_request_line_id.branch_id', string="Branch ID", store=True)
    disbursement_type_id = fields.Many2one(related='disbursement_request_line_id.disbursement_type_id', string="Disbursement Type ID", store=True)
    product_id = fields.Many2one(related='disbursement_request_line_id.product_id', string="Product ID", store=True)
    warehouse_loc_id = fields.Many2one(related='disbursement_request_line_id.warehouse_loc_id', string="Disbursement Type ID", store=True)
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id.id)

    disbursement_amount = fields.Monetary(related='disbursement_request_line_id.disbursement_amount', string='Amount', currency_field='currency_id', store=True)

    state = fields.Selection(selection=state_selection, string="Status", default="draft")
    collection_point = fields.Selection(related='disbursement_request_line_id.collection_point', string="Collection Point", store=True)

    collection_date = fields.Date('Collection Date', default=fields.Date.today())


    def action_disbursed(self):
        if not self.collection_date:
            raise exceptions.ValidationError('Please enter Collection Date')
        
        # if self.disbursement_category_id.name != 'Cash':
            # product_quantity = self.product_id.qty_available
            # if product_quantity > 0:
            #     stock_quant = self.env['stock.quant'].search([
            #         ('location_id', '=', self.warehouse_loc_id.id),
            #         ('product_id', '=',  self.product_id.id),
            #         ('inventory_quantity_auto_apply', '>', 0)
            #     ], limit=1)


            #     if not stock_quant:
            #         raise exceptions.ValidationError('Stock is not available in that location. Kindly select another location')
            #     else:
            #         stock_move = self.env['stock.move'].create({
            #             'name': f'Decrease stock for Loan {self.name}',
            #             'product_id': self.product_id.id,
            #             'product_uom': self.product_id.uom_id.id,
            #             'product_uom_qty': 1,  # Decrease 1 unit
            #             'location_id': self.warehouse_loc_id.id,  # Source location (stock)
            #             'location_dest_id': self.env.ref('stock.stock_location_customers').id,
            #             'state': 'draft',  # Initial state is draft
            #         })
            #         picking = self.env['stock.picking'].create({
            #             'partner_id': self.donee_id.id,  # Link to customer
            #             'picking_type_id': self.env.ref('stock.picking_type_out').id,  # Outgoing picking type
            #             'move_ids_without_package': [(6, 0, [stock_move.id])],  # Associate the stock move with the picking
            #             'origin': self.name
            #         })
            #         stock_move._action_confirm()
            #         stock_move._action_assign()
            #         picking.action_confirm()
            #         picking.button_validate()

            # else:
            #     raise exceptions.ValidationError('Not enough stock available')
        
        move_lines = [
            {
                'name': f'{self.disbursement_type_id.name}',
                'account_id': self.product_id.property_account_income_id.id,
                'credit': self.disbursement_request_line_id.disbursement_amount,
                'debit': 0.0,
                'partner_id': self.donee_id.id,
                'currency_id': self.disbursement_request_line_id.currency_id.id if self.disbursement_request_line_id.currency_id else None,
            },
            {
                'name': f'{self.disbursement_type_id.name}',
                'account_id': self.product_id.property_account_expense_id.id,
                'debit': self.disbursement_request_line_id.disbursement_amount,
                'credit': 0.0,
                'partner_id': self.donee_id.id,
                'currency_id': self.disbursement_request_line_id.currency_id.id if self.disbursement_request_line_id.currency_id else None,
            }
        ]

        move = self.env['account.move'].create({
            'ref': f'{self.disbursement_request_line_id.disbursement_request_id.name} - {self.collection_date}',
            'partner_id': self.donee_id.id,
            # 'journal_id': journal.id,
            'line_ids': [(0, 0, line) for line in move_lines],
            'date': fields.Date.today(),
            'move_type': 'entry',
        })
        move.action_post()

        self.write({'state': 'disbursed'})