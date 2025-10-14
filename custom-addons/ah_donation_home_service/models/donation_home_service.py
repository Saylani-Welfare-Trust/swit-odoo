from odoo import fields,api,models,_

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
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('cheque_deposited', 'Cheque Deposited'),
        ('paid', 'Paid'),
        ('cheque_bounced', 'Bounced'),
        ('cancel', 'Cancelled')],
        string='Status',
        default='draft', copy=False, index=True, readonly=True,
        store=True, tracking=True,
        help=" * Draft: The MFD Loan is not confirmed yet.\n"
             " * Pending: Delivery Receipt has been generated.\n"
             " * Pending: Cheque clearance is Pending.\n"
             " * Paid: Donation has been paid.\n"
             " * Cancelled: Donation has been cancelled.\n"
             " * Bounced: Cheque has been bounced.\n")


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
            'picking_type_id': self.env.ref('stock.picking_type_out').id,
            'origin': self.name,
            'is_donation_home_service': True,
            'dhs_id': self.id
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
            move._action_confirm()
            move._action_assign()

        picking.action_confirm()
        self.write({'picking_id': picking.id})
        self.write({'state': 'pending'})

    def deposit_cheque(self):
        self.write({'state': 'cheque_deposited'})

    def bounce_cheque(self):
        self.write({'state': 'cheque_bounced'})

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
        print(data)
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
        print(data, 'data')
        print(is_cancel, 'is_cancel')
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
            donation_id.confirm_payment()

        return {
            "status": "success",
            "donation_id": donation_id.id,
        }



class AdvanceDonationLine(models.Model):
    _name = 'donation.home.service.line'

    def _get_product_ids(self):
        records = self.env['dhs.product.conf'].sudo().search([])
        product_ids = records.mapped('product_id.id')
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



