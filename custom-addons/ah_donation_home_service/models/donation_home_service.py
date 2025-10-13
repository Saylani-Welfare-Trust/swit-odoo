from odoo import fields,api,models,_
from odoo import models, fields, api, _
from odoo.exceptions import UserError


import logging

_logger = logging.getLogger(__name__)

class AdvanceDonation(models.Model):
    _name = 'donation.home.service'

    name = fields.Char(string="Name", required=True, copy=False, readonly=True, default=lambda self: _('New'))
    partner_id = fields.Many2one('res.partner', 'Customer')
    address = fields.Char('Address')
    phone_no = fields.Char('Phone Number')
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)
    payment_type = fields.Selection([('cash', 'Cash'), ('cheque', 'Cheque')], string='Payment Type', default='cash')

    bank_id = fields.Char(string='Bank Name')
    cheque_number = fields.Char(string='Cheque Number')
    cheque_date = fields.Date(string='Cheque Date')

    subtotal = fields.Monetary('SubTotal', currency_field='currency_id')
    delivery_charges = fields.Monetary('Service Charges', currency_field='currency_id')
    total_amount = fields.Monetary('Total', currency_field='currency_id')

    donation_product_lines = fields.One2many('donation.home.service.line', 'donation_id')

    picking_id = fields.Many2one('stock.picking')
    state = fields.Selection([
       
        ('pending', 'Pending'),
        ('gat_pass', 'Gate Pass'),
        ('gat_in', 'Gate In'),
         ('paid','Paid'),
        ('slotter', 'Slotter'),
        ('cancel', 'Cancelled')],
        string='Status',
        default='pending', copy=False, index=True, readonly=True,
        store=True, tracking=True,
        help=" * Draft: The MFD Loan is not confirmed yet.\n"
             " * Pending: Delivery Receipt has been generated.\n"
             " * Pending: Cheque clearance is Pending.\n"
             " * Paid: Donation has been paid.\n"
             " * Cancelled: Donation has been cancelled.\n"
             " * Bounced: Cheque has been bounced.\n")
    # @api.model
    # def fetch_dhs_products(self, dhs_name):
    #     """Fetch DHS record by name and return product information"""
    #     # Search for the DHS record
    #     dhs_record = self.search([('name', '=', dhs_name),('state', '!=', 'paid')], limit=1)

        
    #     if not dhs_record:
    #         raise UserError(_('Donation Home Service record with reference %s not found.') % dhs_name)
        
    #     if dhs_record.state not in ['gat_pass', 'gat_in']:
    #         raise UserError(_('Donation Home Service %s is not in a valid state.') % dhs_record.name)
        
    #     # Prepare product data for POS
    #     products_data = []
    #     for line in dhs_record.donation_product_lines:
    #         product = line.product_id
    #         products_data.append({
    #             'product_id': product.id,
    #             'name': product.name,
    #             'quantity': line.quantity,
    #             'price': product.lst_price,
    #             'default_code': product.default_code ,
    #             'category': product.categ_id.name if product.categ_id else '',
    #         })
        
    #     return {
    #         'dhs_id': dhs_record.id,
    #         'dhs_name': dhs_record.name,
    #         'partner_id': dhs_record.partner_id.id if dhs_record.partner_id else False,
    #         'partner_name': dhs_record.partner_id.name if dhs_record.partner_id else '',
    #         'products': products_data,
    #         'success': True
    #     }


    # @api.model
    # def fetch_dhs_products(self, dhs_name):
    #     """Fetch DHS record by name and return product information"""
    #     # Search for the DHS record
    #     dhs_record = self.search([('name', '=', dhs_name), ('state', '!=', 'paid')], limit=1)
        
    #     if not dhs_record:
    #         raise UserError(_('Donation Home Service record with reference %s not found.') % dhs_name)
        
    #     if dhs_record.state not in ['gat_pass', 'gat_in']:
    #         raise UserError(_('Donation Home Service %s is not in a valid state.') % dhs_record.name)
        
    #     # Use gate_in location for DHS orders
    #     gate_in_location = self.env.ref('__custom__.gate_in_location', False)

    #     scan_card_picking_type = self.env.ref('__custom__.	__custom__.live_stock', False)
    #     if not scan_card_picking_type:
    #         # Fallback to default POS operation type
    #         scan_card_picking_type = self.env['stock.picking.type'].search([
    #             ('name', '=', 'live stock pos')
    #         ], limit=1) 
        
    #     source_location_id = gate_in_location.id if gate_in_location else False
    #     picking_type_id = scan_card_picking_type.id

    #     _logger.info("Gate In Location ID: %s", source_location_id,gate_in_location)
        
    #     # Prepare product data for POS
    #     products_data = []
        
    #     # Add regular product lines
    #     for line in dhs_record.donation_product_lines:
    #         product = line.product_id
    #         products_data.append({
    #             'product_id': product.id,
    #             'name': product.name,
    #             'quantity': line.quantity,
    #             'price': product.lst_price,
    #             'default_code': product.default_code,
    #             'category': product.categ_id.name if product.categ_id else '',
    #             'source_location_id': source_location_id,
    #             'is_dhs_product': True, 
    #              'picking_type_id': picking_type_id, # Flag to identify DHS products
    #         })
        
    #     # Add delivery charges if applicable
    #     delivery_charges = dhs_record['delivery_charges']
        
    #     if delivery_charges and float(delivery_charges) > 0:
    #         service_product = self.env['product.product'].search([
    #             ('name', 'ilike', 'delivery service'),
    #             ('type', '=', 'service'),
    #             ('available_in_pos', '=', True)
    #         ], limit=1)
            
    #         if service_product:
    #             products_data.append({
    #                 'product_id': service_product.id,
    #                 'name': service_product.name,
    #                 'quantity': 1,
    #                 'price': float(delivery_charges),
    #                 'default_code': service_product.default_code,
    #                 'category': service_product.categ_id.name if service_product.categ_id else 'Services',
    #                 'picking_type_id': picking_type_id,
                
    #                 'source_location_id': source_location_id,
                   
    #             })
    #     _logger.info("Products Data: %s", products_data)
        
    #     return {
    #         'dhs_id': dhs_record.id,
    #         'dhs_name': dhs_record.name,
    #         'partner_id': dhs_record.partner_id.id if dhs_record.partner_id else False,
    #         'partner_name': dhs_record.partner_id.name if dhs_record.partner_id else '',
    #         'delivery_charges': float(delivery_charges),
    #         'source_location_id': source_location_id,
    #         'products': products_data,
    #         'success': True,
    #         'is_dhs_order': True,  # Flag to identify DHS order
    #     }
    


    
    # @api.model
    # def update_dhs_state_to_paid(self, dhs_name):
    #     """Update DHS state from 'gat_pass' to 'paid'"""
    #     # Search for the DHS record
    #     # dhs_record = self.search([('name', '=', dhs_name)], limit=1)
    #     dhs_record = self.search([
    #         ('name', '=', dhs_name),
    #         ('state', '!=', 'paid')
    #     ], limit=1)
        
    #     if not dhs_record:
    #         raise UserError(_('Donation Home Service record with reference %s not found.') % dhs_name)
        
    #     if dhs_record.state not in['gat_pass', 'gat_in']:
    #         raise UserError(_('Donation Home Service %s is not in gat_pass state. Current state: %s') % 
    #                       (dhs_record.name, dhs_record.state))
    #     if dhs_record.state =='paid':
    #         raise UserError(_('Donation Home Service %s is  already in paid state. Current state: %s') % 
    #                       (dhs_record.name, dhs_record.state))
        
    #     # Update state to paid
    #     dhs_record.write({'state': 'paid'})
        
    #     return {
    #         'success': True,
    #         'message': _('DHS %s state updated to paid successfully.') % dhs_record.name
    #     }
    
    @api.model
    def fetch_dhs_products(self, dhs_name):
        """Fetch DHS record by name and return product information"""
        # Search for the DHS record
        dhs_record = self.search([('name', '=', dhs_name), ('state', '!=', 'paid')], limit=1)
        
        if not dhs_record:
            raise UserError(_('Donation Home Service record with reference %s not found.') % dhs_name)
        
        if dhs_record.state not in ['gat_pass', 'gat_in']:
            raise UserError(_('Donation Home Service %s is not in a valid state.') % dhs_record.name)
        # Use gate_in location for DHS orders
        gate_in_location = self.env.ref('__custom__.gate_in_location', False)

        
       
        # Get custom operation type for scan card orders
        scan_card_picking_type = self.env.ref('__custom__.live_stock', False)
        if not scan_card_picking_type:
            # Fallback to default POS operation type
            scan_card_picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'outgoing'),
                ('name', 'ilike', 'scan card')
            ], limit=1) or self.env['pos.config'].get_default_config().picking_type_id
        
        source_location_id = gate_in_location.id
        picking_type_id = scan_card_picking_type.id
        
        # Prepare product data for POS
        products_data = []
        
        # Add regular product lines
        for line in dhs_record.donation_product_lines:
            product = line.product_id
            products_data.append({
                'product_id': product.id,
                'name': product.name,
                'quantity': line.quantity,
                'price': product.lst_price,
                'default_code': product.default_code,
                'category': product.categ_id.name if product.categ_id else '',
                'source_location_id': source_location_id,
                'picking_type_id': picking_type_id,  # Add picking type to each product
            })
        
        # Add delivery charges if applicable
        delivery_charges = getattr(dhs_record, 'delivery_charges', 0.0)
        
        if delivery_charges and float(delivery_charges) > 0:
            service_product = self.env['product.product'].search([
                ('name', '=', 'service charges'),
                ('type', '=', 'service'),
                ('available_in_pos', '=', True)
            ], limit=1)
            
            if service_product:
                products_data.append({
                    'product_id': service_product.id,
                    'name': service_product.name,
                    'quantity': 1,
                    'price': float(delivery_charges),
                    'default_code': service_product.default_code or 'DELIVERY',
                    'category': service_product.categ_id.name if service_product.categ_id else 'Services',
                    'is_delivery_charge': True,
                    'source_location_id': source_location_id,
                    'picking_type_id': picking_type_id,  # Add picking type to delivery charge
                })
        
        return {
            'dhs_id': dhs_record.id,
            'dhs_name': dhs_record.name,
            'partner_id': dhs_record.partner_id.id if dhs_record.partner_id else False,
            'partner_name': dhs_record.partner_id.name if dhs_record.partner_id else '',
            'delivery_charges': float(delivery_charges),
            'source_location_id': source_location_id,
            'picking_type_id': picking_type_id,  # Add picking type to main response
            'products': products_data,
            'success': True
        }

    





    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('donation.home.service') or ('New')
        return super().create(vals)

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        if self.partner_id:
            address = ''
            if self.partner_id.street:
                address += self.partner_id.street
            if self.partner_id.street2:
                address += ' '+self.partner_id.street2
            if self.partner_id.city:
                address += ' ' + self.partner_id.city
            if self.partner_id.state_id:
                address += ' ' + self.partner_id.state_id.name
            self.address = address
            self.phone_no = self.partner_id.mobile


    @api.onchange('subtotal', 'delivery_charges')
    def onchange_delivery_charges(self):
        self.total_amount = self.subtotal + self.delivery_charges

    @api.onchange('donation_product_lines')
    def onchange_product_amount(self):
        self.subtotal = sum(line.amount for line in self.donation_product_lines)


    def confirm_donation(self):
        picking = self.env['stock.picking'].create({
            'partner_id': self.partner_id.id,
            'picking_type_id': self.env.ref('__custom__Donation_home_service.Donation_home_service').id,
            'origin': self.name,
            'is_donation_home_service': True,
            'dhs_id': self.id,
            'state' : 'draft',
        })

        for line in self.donation_product_lines:
            if line.product_id.detailed_type == 'product':
                stock_move = self.env['stock.move'].create({
                    'name': f'Reserve for DHS {self.name}',
                    'product_id': line.product_id.id,
                    'product_uom': line.product_id.uom_id.id,
                    'product_uom_qty': line.quantity,
                    'location_id': self.env.ref('stock.stock_location_stock').id,
                    'location_dest_id': self.env.ref('stock.stock_location_customers').id,
                    'state': 'draft',
                    'picking_id': picking.id
                })

        for move in picking.move_ids:
           
            move._action_assign()

        picking.action_confirm()
        self.write({'picking_id': picking.id})
        self.write({'state': 'pending'})

  



    def cancel_donation(self):
        self.write({'state': 'cancel'})

    def confirm_payment(self):
        credit_account_one = self.env.ref('ah_donation_home_service.credit_account_one').account_id
        debit_account_one = self.env.ref('ah_donation_home_service.debit_account_one').account_id

        move_lines = [
            {
                'name': f'{self.name}',
                'account_id': credit_account_one.id,
                'credit': self.total_amount,
                'debit': 0.0,
                'partner_id': self.partner_id.id,
                'currency_id': self.currency_id.id if self.currency_id else None,
            },
            {
                'name': f'{self.name}',
                'account_id': debit_account_one.id,
                'debit': self.total_amount,
                'credit': 0.0,
                'partner_id': self.partner_id.id,
                'currency_id': self.currency_id.id if self.currency_id else None,
            }
        ]

        move = self.env['account.move'].create({
            'ref': f'{self.name}',
            'partner_id': self.partner_id.id,
            # 'journal_id': journal.id,
            'line_ids': [(0, 0, line) for line in move_lines],
            'date': fields.Date.today(),
            'move_type': 'entry',
        })

        move.action_post()

        credit_account_two = self.env.ref('ah_donation_home_service.credit_account_two').account_id
        debit_account_two = self.env.ref('ah_donation_home_service.debit_account_two').account_id

        move_lines = [
            {
                'name': f'{self.name}',
                'account_id': credit_account_two.id,
                'credit': self.total_amount,
                'debit': 0.0,
                'partner_id': self.partner_id.id,
                'currency_id': self.currency_id.id if self.currency_id else None,
            },
            {
                'name': f'{self.name}',
                'account_id': debit_account_two.id,
                'debit': self.total_amount,
                'credit': 0.0,
                'partner_id': self.partner_id.id,
                'currency_id': self.currency_id.id if self.currency_id else None,
            }
        ]

        move = self.env['account.move'].create({
            'ref': f'{self.name}',
            'partner_id': self.partner_id.id,
            # 'journal_id': journal.id,
            'line_ids': [(0, 0, line) for line in move_lines],
            'date': fields.Date.today(),
            'move_type': 'entry',
        })

        move.action_post()


        # self.picking_id.button_validate()
        self.write({'state': 'paid'})



    # POS Functions

    @api.model
    def register_pos_donation(self, data):
        donation_product_lines = []
        for line in data['order_lines']:
            # Assuming 'product_id' is a valid product ID
            donation_product_lines.append((0, 0, {
                'product_id': line['product_id'],
                'quantity': line['quantity'],
            }))
        donation = self.env['donation.home.service'].create({
            'partner_id': data['partner_id'],
            'payment_type': data['payment_type'],
            'delivery_charges': data['delivery_charges'],
            'donation_product_lines': donation_product_lines
        })
        donation.onchange_partner_id()
        for line in donation.donation_product_lines:
            line.onchange_product_id()

        donation.onchange_product_amount()
        donation.onchange_delivery_charges()

        donation.confirm_donation()
       
        # print('record created')
        return{
            "status": "success",
            "donation_id": donation.id
        }

    @api.model
    def check_donation_id(self, data, is_cancel):
        # _logger.info("=== POS PAYMENT CONFIRMATION STARTED ===")
        # _logger.info("Received data: %s",donation_id.read())
      
        # _logger.info("Donation ID value from data: %s", data['donation_id'])
        
        # # Log more details if needed
        # _logger.debug("Full donation record: %s", donation_id)
        # print(data, 'data')
        # print(is_cancel, 'is_cancel')
        if not data:
            return {
                "status": "error",
                "body": "Please enter Donation ID",
            }

        donation_id = self.sudo().search([('name', '=', data)])

        if not donation_id:
            return {
                "status": "error",
                "body": "Record not found",
            }

        if donation_id.state not in 'pending':
            return {
                "status": "error",
                "body": f"Donation is currently in {donation_id.state} state",
            }

        if donation_id.state == 'pending' and is_cancel == True:
            donation_id.cancel_donation()
            return{
                "status": "success",
                "body": "Donation has been cancelled"
            }
        
        

        return {
            "status": "success",
            "donation_id": donation_id.id,
            "donation_name": donation_id.name,
            "donation_amount": donation_id.total_amount,
            "payment_type": donation_id.payment_type
        }

    @api.model
    def confirm_pos_payment(self, data):
        donation_id = self.sudo().search([('id', '=', data['donation_id'])])
        

        if data['payment_type'] == 'cheque':
            if not data['bank_name']:
                return {
                    "status": "error",
                    "body": "Please select bank",
                }
            if not data['cheque_number']:
                return {
                    "status": "error",
                    "body": "Please enter cheque number",
                }
            if not data['cheque_date']:
                return {
                    "status": "error",
                    "body": "Please enter cheque date",
                }
            donation_id.write({
                'payment_type': data['payment_type'],
                'bank_id': data['bank_name'],
                'cheque_number': data['cheque_number'],
                'cheque_date': data['cheque_date']
            })
            donation_id.deposit_cheque()
        else:
            donation_id.write({'payment_type': data['payment_type']})
            # donation_id.confirm_payment()

        
        



class AdvanceDonationLine(models.Model):
    _name = 'donation.home.service.line'

    def _get_product_ids(self):
        records = self.env['product.product'].sudo().search([('check_stock', '=', True)])
        product_ids = records.ids
        
        # product_ids = records.mapped('product_id.id')
        return [('id', 'in', product_ids)]

    product_id = fields.Many2one('product.product', 'Product', domain=_get_product_ids)
    quantity = fields.Integer('Quantity', default=1)
    amount = fields.Monetary('Amount', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='donation_id.currency_id')
    product_pric_incl_tax = fields.Monetary('Total Amount', currency_field='currency_id' )
    donation_id = fields.Many2one('donation.home.service')


    @api.onchange('product_id', 'quantity')
    def onchange_product_id(self):
        if self.product_id:
            base_price = self.product_id.lst_price
            taxes = self.product_id.taxes_id
            print(taxes)
            total_price_incl_tax = base_price

            for tax in taxes:
                if tax.amount_type == 'percent':
                    tax_amount = base_price * (tax.amount / 100)
                    print(tax_amount, 'tax_amount')
                    total_price_incl_tax += tax_amount
                else:
                    total_price_incl_tax += tax.amount

            self.product_pric_incl_tax = total_price_incl_tax
            self.amount = self.product_pric_incl_tax * self.quantity
  








class PosOrder(models.Model):
    _inherit = 'pos.order'

    source_location_id = fields.Many2one('stock.location', string='Source Location')
    is_dhs_order = fields.Boolean(string='Is DHS Order', default=False)
    picking_type_id = fields.Many2one('stock.picking.type', string='Picking Type')
    is_scan_card_order = fields.Boolean(string='Is Scan Card Order', default=False)

    @api.model
    def _order_fields(self, ui_order):
        order_fields = super(PosOrder, self)._order_fields(ui_order)
        
        # Only set custom source location for DHS orders
        if ui_order.get('is_dhs_order') and ui_order.get('source_location_id'):
            order_fields['source_location_id'] = ui_order['source_location_id']
            order_fields['is_dhs_order'] = True

        
        if ui_order.get('source_location_id'):
                order_fields['source_location_id'] = ui_order['source_location_id']
        if ui_order.get('is_scan_card_order'):
            order_fields['is_scan_card_order'] = ui_order['is_scan_card_order']
        
        return order_fields

    def _create_order_picking(self):
        # For scan card orders, use custom location and operation type logic
        if self.is_scan_card_order and self.source_location_id and self.picking_type_id:
            return self._create_scan_card_picking()
        else:
            # Use normal POS flow for regular orders
            return super(PosOrder, self)._create_order_picking()


    # def _create_dhs_picking(self):
    #     raise UserError(_("DHS Picking creation is currently disabled."))
    #     """Create picking specifically for DHS orders using gate_in location"""
    #     self.ensure_one()
        
    #     picking_type = self.config_id.picking_type_id
    #     source_location = self.source_location_id
        # dest_location = self.partner_id.property_stock_customer if self.partner_id else picking_type.default_location_dest_id
        
        # # Create the picking
        # picking_vals = {
        #     'picking_type_id': picking_type.id,
        #     'partner_id': self.partner_id.id,
        #     'origin': self.name,
        #     'location_dest_id': dest_location.id,
        #     'location_id': source_location.id,
        # }
        
        # picking = self.env['stock.picking'].create(picking_vals)
        # _logger.info("Created DHS Picking: %s", picking.name)
        # _logger.info("Created DHS Picking: %s", picking_vals)
        # _logger.info("Source Location: %s", source_location.name)
        # _logger.info("Destination Location: %s", dest_location.name)
        # _logger.info("Order Lines: %s", picking)
        
        # # Create move lines
        # moves = self.env['stock.move']
        # for line in self.lines:
        #     move_vals = {
        #         'name': line.name,
        #         'product_id': line.product_id.id,
        #         'product_uom_qty': line.qty,
        #         'product_uom': line.product_id.uom_id.id,
        #         'picking_id': picking.id,
        #         'location_id': source_location.id,
        #         'location_dest_id': dest_location.id,
        #     }
        #     moves.create(move_vals)
        
        # # Confirm and assign the picking
        # picking.action_confirm()
        # picking.action_assign()
        
        # return picking
    
    def _create_scan_card_picking(self):
        """Create picking specifically for scan card orders using live_stock location"""
        self.ensure_one()
        
        picking_type = self.picking_type_id
        source_location = self.source_location_id
        
        # Use customer location as destination
        if self.partner_id and self.partner_id.property_stock_customer:
            dest_location = self.partner_id.property_stock_customer
        else:
            dest_location = picking_type.default_location_dest_id
        
        # Create the picking with custom source location and operation type
        picking_vals = {
            'picking_type_id': picking_type.id,
            'partner_id': self.partner_id.id if self.partner_id else False,
            'origin': f"Scan Card Order: {self.name}",
            'location_dest_id': dest_location.id,
            'location_id': source_location.id,
            'note': f"Scan Card DHS Order: {self.name}",
        }
        
        picking = self.env['stock.picking'].create(picking_vals)
        
        # Create move lines
        moves = self.env['stock.move']
        for line in self.lines:
            move_vals = {
                'name': line.name,
                'product_id': line.product_id.id,
                'product_uom_qty': line.qty,
                'product_uom': line.product_id.uom_id.id,
                'picking_id': picking.id,
                'location_id': source_location.id,
                'location_dest_id': dest_location.id,
            }
            moves.create(move_vals)
        
        # Confirm and assign the picking
        picking.action_confirm()
        picking.action_assign()
        
        return picking
