from odoo import models, fields,api
# from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


state_selection = [
    ('draft', 'Draft'),
    ('delivered', 'Delivery Created'),
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
    analytic_account_domain = fields.Char('Analytic Account Domain', compute='_compute_analytic_account_domain', default="[]", store=True)
    disbursement_category_id = fields.Many2one('disbursement.category', string="Disbursement Category")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)
    disbursement_application_type_id = fields.Many2one('disbursement.application.type', string="Disbursement Application Type")
    # warehouse_id = fields.Many2one('stock.warehouse', string="Warehouse")
    # warehouse_domain = fields.Char('Warehouse Domain', compute='_compute_warehouse_domain', default="[]", store=True)
    bill_id = fields.Many2one('account.move', string="Bill", readonly=True)

    collection_point = fields.Selection(selection=collection_point_selection, string="Collection Point")

    collection_date = fields.Date('Collection Date', default=fields.Date.today())

    amount = fields.Monetary('Amount', currency_field='currency_id')
    quantity = fields.Float('Quantity', default=1.0)
    state = fields.Selection(selection=state_selection, string="State", default='draft')
    
    show_deliver_button = fields.Boolean(string="Show Deliver Button", compute='_compute_show_deliver_button', store=False)
    
    @api.model
    def _auto_mark_as_delivered_today(self):
        today = fields.Date.today()
        lines = self.search([('collection_date', '=', today), 
                             ('state', '=', 'draft'),
                             ('disbursement_category_id', '=', self.env.ref('bn_master_setup.disbursement_category_in_kind').id),
                            ('welfare_id.state', '=', 'approve'),
                            ('collection_point', '=', 'branch'),
                            ('welfare_id.order_type', 'in', ['one_time'])
                            ])
        # _logger.info(f"rec_line: {lines.read()}")
        for line in lines:
            if line.welfare_id.order_type == 'recurring':
                try:
                    line.action_delivered()
                except Exception as e:
                    # Optionally log error
                    pass
    
    @api.model
    def _auto_create_bills_for_cash_bank(self):
        """Scheduled action to create bills for Cash + Bank collection on collection date"""
        today = fields.Date.today()
        cash_category = self.env.ref('bn_master_setup.disbursement_category_Cash', raise_if_not_found=False)
        
        if not cash_category:
            return
        
        lines = self.search([
            ('collection_date', '=', today),
            ('state', '=', 'draft'),
            ('disbursement_category_id', '=', cash_category.id),
            ('collection_point', '=', 'bank'),
            ('bill_id', '=', False),
            ('welfare_id.state', '=', 'approve'),
            ('welfare_id.order_type', 'in', ['recurring'])

        ])
        
        for line in lines:
            try:
                line._create_bill()
                line.state = 'delivered'  # Mark as disbursed immediately after bill creation for Cash + Bank
            except Exception as e:
                # Log error but continue processing other lines
                pass
    
    def _create_bill(self):
        """Create vendor bill for Cash + Bank collection"""
        if not self.welfare_id.donee_id:
            return
        
        # Get expense account from product or use default
        account = self.product_id.property_account_expense_id or \
                  self.product_id.categ_id.property_account_expense_categ_id
        
        if not account:
            # Get default payable account
            account = self.env['account.account'].search([
                ('account_type', '=', 'expense')
            ], limit=1)
        
        invoice_line_vals = {
            'product_id': self.product_id.id,
            'name': self.product_id.name or 'Welfare Payment',
            'quantity': self.quantity,
            'price_unit': self.amount,
            'account_id': account.id if account else False,
            'analytic_account_id': self.analytic_account_id.id if self.analytic_account_id else False,
        }
        
        bill_vals = {
            'move_type': 'in_invoice',
            'partner_id': self.welfare_id.donee_id.id,
            'invoice_date': self.collection_date,
            'date': self.collection_date,
            'ref': self.name,
            'invoice_line_ids': [(0, 0, invoice_line_vals)],
            'recurring_line_id': self.id,
        }
        
        bill = self.env['account.move'].create(bill_vals)
        self.bill_id = bill.id
        
        # Auto-post the bill
        bill.action_post()
        
        return bill

    def action_disbursed(self):
        # Mark as disbursed and update welfare if all lines are delivered/disbursed
        self.state = 'disbursed'
        
        # # For Cash + Bank, check if bill is paid
        # cash_category = self.env.ref('bn_master_setup.disbursement_category_Cash', raise_if_not_found=False)
        # if cash_category and self.disbursement_category_id.id == cash_category.id:
        #     if self.collection_point == 'bank' and self.bill_id:
        #         # Bill payment is handled through account.move payment
        #         # This method will be called after payment is registered
        #         pass
        
        if self.welfare_id:
            self.welfare_id._auto_disburse_if_all_lines_delivered()
    
    @api.depends('welfare_id')
    def _compute_name(self):
            for rec in self:
                rec.name = rec.welfare_id.name if rec.welfare_id else ''
    
    @api.depends('disbursement_application_type_id')
    def _compute_analytic_account_domain(self):
        for rec in self:
            rec.analytic_account_domain = ""
            if rec.disbursement_application_type_id and rec.disbursement_application_type_id.analytic_account_ids:
                analytic_account_ids = rec.disbursement_application_type_id.analytic_account_ids.ids
                rec.analytic_account_domain = str([('id', 'in', analytic_account_ids)])
    
    @api.onchange('disbursement_category_id')
    def _onchange_disbursement_category_id(self):
        """Auto-select branch for In Kind category"""
        in_kind_category = self.env.ref('bn_master_setup.disbursement_category_in_kind', raise_if_not_found=False)
        if in_kind_category and self.disbursement_category_id.id == in_kind_category.id:
            self.collection_point = 'branch'
    
    @api.depends('disbursement_category_id', 'state')
    def _compute_show_deliver_button(self):
        in_kind_category = self.env.ref('bn_master_setup.disbursement_category_in_kind', raise_if_not_found=False)
        cash_category = self.env.ref('bn_master_setup.disbursement_category_Cash', raise_if_not_found=False)
        for rec in self:
            rec.show_deliver_button = False
            if rec.disbursement_category_id:
                if in_kind_category and rec.disbursement_category_id.id == in_kind_category.id:
                    # Only show if state is not delivered or disbursed
                    if rec.state not in ['delivered', 'disbursed']:
                        rec.show_deliver_button = True
                elif cash_category and rec.disbursement_category_id.id == cash_category.id:
                    rec.show_deliver_button = False

    def action_delivered(self):
            in_kind_category = self.env.ref('bn_master_setup.disbursement_category_in_kind')
            if self.disbursement_category_id == in_kind_category:        
                StockPicking = self.env['stock.picking']
                StockMove = self.env['stock.move']
                StockMoveLine = self.env['stock.move.line']
                
                # Use warehouse from welfare recurring line, fallback to default
                if self.warehouse_id:
                    warehouse = self.warehouse_id
                    picking_type = warehouse.out_type_id
                    location_src = warehouse.lot_stock_id
                else:
                    picking_type = self.env.ref('stock.picking_type_out')
                    location_src = self.env['stock.location'].search([('usage', '=', 'internal')], limit=1)
                
                location_dest = self.env['stock.location'].search([('usage', '=', 'customer')], limit=1)
                
                picking_vals = {
                    'partner_id': self.donee_id.id,
                    'picking_type_id': picking_type.id,
                    'location_id': location_src.id if location_src else False,
                    'location_dest_id': location_dest.id if location_dest else False,
                    'origin': self.name,
                    'recurring_line_id': self.id,
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
                }
                StockMoveLine.create(move_line_vals)
                picking.action_assign()
                self.state = 'delivered'