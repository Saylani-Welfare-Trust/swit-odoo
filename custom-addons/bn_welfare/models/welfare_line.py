from odoo import models, fields, api


collection_point_selection = [
    ('bank', 'Bank'),
    ('branch', 'Branch'),
]

order_type_selection = [
    ('one_time', 'One Time'),
    ('recurring', 'Recurring'),
    ('both', 'Both'),
]


state_selection = [
    ('draft', 'Draft'),
    ('delivered', 'Delivered'),
    ('disbursed', 'Disbursed'),
]

recurring_duration_selection = [
    ('3_M', '3 Months'),
    ('4_M', '4 Months'),
    ('5_M', '5 Months'),
    ('6_M', '6 Months'),
    ('7_M', '7 Months'),
    ('8_M', '8 Months'),
    ('9_M', '9 Months'),
    ('10_M', '10 Months'),
    ('11_M', '11 Months'),
    ('12_M', '12 Months'),
]


class WelfareLine(models.Model):
    _name = 'welfare.line'
    _description = "Welfare Line"


    product_domain = fields.Char('Product Domain', compute='_compute_product_domain', default="[]", store=True)

    order_type = fields.Selection(selection=order_type_selection, string="Order Type")
    collection_point = fields.Selection(selection=collection_point_selection, string="Collection Point")
    recurring_duration = fields.Selection(selection=recurring_duration_selection, string="Recurring Duration")
    state = fields.Selection(selection=state_selection, string="State")

    welfare_id = fields.Many2one('welfare', string="Welfare")
    product_id = fields.Many2one('product.product', string="Product")
    analytic_account_id = fields.Many2one('account.analytic.account', string="Branch")
    disbursement_category_id = fields.Many2one('disbursement.category', string="Disbursement Category")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)
    disbursement_application_type_id = fields.Many2one('disbursement.application.type', string="Disbursement Application Type")

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )
    fixed_amount_check = fields.Boolean('Fixed Amount Check', default=False, compute='_compute_fixed_amount_check')
    show_deliver_button = fields.Boolean(string="Show Deliver Button", compute='_compute_show_deliver_button', store=False)

    marriage_date = fields.Date('Marriage Date', default=fields.Date.today())
    collection_date = fields.Date('Collection Date', default=fields.Date.today())
    quantity = fields.Float('Quantity', default=1.0)
    amount = fields.Float(
        'Amount',
        related='product_id.list_price',
        store=True,
    )

    total_amount = fields.Float(
        'Total Amount',
        compute='_compute_total_amount',
        store=True
    )
    
    @api.depends('disbursement_category_id', 'order_type')
    def _compute_show_deliver_button(self):
        in_kind_category = self.env.ref('bn_master_setup.disbursement_category_in_kind', raise_if_not_found=False)
        cash_category = self.env.ref('bn_master_setup.disbursement_category_Cash', raise_if_not_found=False)
        for rec in self:
            rec.show_deliver_button = False
            if rec.disbursement_category_id:
                if rec.welfare_id.state == 'approve':
                    if in_kind_category and rec.disbursement_category_id.id == in_kind_category.id:
                        # Only show if state is not delivered or disbursed
                        if rec.order_type == "one_time" and rec.state not in ['delivered', 'disbursed']:
                            rec.show_deliver_button = True
                    elif cash_category and rec.disbursement_category_id.id == cash_category.id:
                        rec.show_deliver_button = False
                else:
                    rec.show_deliver_button = False
                
                    
    @api.depends('disbursement_category_id')
    def _compute_fixed_amount_check(self):
        for rec in self:
            rec.fixed_amount_check = rec.disbursement_category_id.name =="In Kind"

    @api.depends('quantity', 'amount')
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = rec.quantity * rec.amount
            
    @api.depends('disbursement_application_type_id')
    def _compute_product_domain(self):
        for rec in self:
            rec.product_domain = ""

            category_id = rec.disbursement_application_type_id.product_category_id.id
            
            if category_id:
                rec.product_domain = str([('categ_id', '=', category_id), ('is_welfare', '=', True)])
                
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
                    'partner_id': self.welfare_id.donee_id.id,
                    'picking_type_id': self.env.ref('stock.picking_type_out').id,
                    'location_id': location_src.id if location_src else False,
                    'location_dest_id': location_dest.id if location_dest else False,
                    'origin': self.welfare_id.name,
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
                    'welfare_line_id': self.id,
                }
                StockMoveLine.create(move_line_vals)
                picking.action_assign()
                self.state = 'delivered'