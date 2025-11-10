from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


status_selection = [       
    ('draft', 'Draft'),
    ('gate_out', 'Gate Out'),
    ('gate_in', 'Gate In'),
    ('paid','Paid'),
    ('slotter', 'Slotter'),
    ('cancel', 'Cancelled')
]


class DonationHomeService(models.Model):
    _name = 'donation.home.service'
    _description = "Donation Home Service"


    donor_id = fields.Many2one('res.partner', string="Donee")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)
    picking_id = fields.Many2one('stock.picking', string="Stock Picking")
    second_picking_id = fields.Many2one('stock.picking', string="Stock Picking")

    name = fields.Char('Name', default="New")
    mobile = fields.Char(related='donor_id.mobile', string="Mobile No.")

    address = fields.Text('Address')

    state = fields.Selection(selection=status_selection, string="Status", default="draft")

    amount = fields.Monetary('Amount', currency_field='currency_id')
    total_amount = fields.Monetary('Total Amount', currency_field='currency_id')
    service_charges = fields.Monetary('Service Charges', currency_field='currency_id')

    donation_home_service_line_ids = fields.One2many('donation.home.service.line', 'donation_home_service_id', string="Donation Home Services")


    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('donation_home_service') or ('New')

        return super(DonationHomeService, self).create(vals)
    
    def calculate_amount(self):
        self.amount = sum(line.amount for line in self.donation_home_service_line_ids)

    def calculate_service_charges(self):
        self.total_amount = self.amount + self.service_charges

    def action_confirm(self):
        """Confirm donation and create stock picking if product-type lines exist."""
        StockPicking = self.env['stock.picking']
        StockMove = self.env['stock.move']
        StockLocation = self.env.ref('stock.stock_location_stock')
        GateOutLocation = self.env.ref('bn_donation_home_service.gate_out_location')
        PickingType = self.env.ref('bn_donation_home_service.donation_home_service_out_stock_picking_type')

        for record in self:
            product_lines = record.donation_home_service_line_ids.filtered(
                lambda l: l.product_id.detailed_type != 'service'
            )

            if not product_lines:
                continue  # skip if no stockable products

            # ✅ Create the picking
            picking = StockPicking.create({
                'partner_id': record.donor_id.id,
                'picking_type_id': PickingType.id,
                'origin': record.name,
                'dhs_id': record.id,
                'state': 'draft',
            })

            # ✅ Create all stock moves in bulk for efficiency
            moves_vals = [{
                'name': f'Gate Out against {record.name}',
                'product_id': line.product_id.id,
                'product_uom': line.product_id.uom_id.id,
                'product_uom_qty': line.quantity,
                'location_id': StockLocation.id,
                'location_dest_id': GateOutLocation.id,
                'picking_id': picking.id,
                'state': 'draft',
            } for line in product_lines]

            StockMove.create(moves_vals)

            # ✅ Assign and confirm moves properly
            picking.action_assign()
            picking.action_confirm()

            # ✅ Link picking back to record
            record.picking_id = picking.id     
    
    def action_cancel(self):
        """Cancel Donation Home Service and associated pickings safely"""

        # Cancel the main picking
        if self.picking_id:
            if self.picking_id.state == 'done':
                # Create a return picking to reverse the done picking
                return_picking = self.picking_id._create_returns()
                return_picking.action_confirm()
                for move in return_picking.move_ids:
                    move.quantity_done = move.product_uom_qty
                return_picking.button_validate()
            elif self.picking_id.state not in ['cancel', 'done']:
                self.picking_id.action_cancel()

        # Cancel the second picking (return / gate in)
        if self.second_picking_id:
            if self.second_picking_id.state == 'done':
                # Optionally, create a return for the done picking
                return_picking = self.second_picking_id._create_returns()
                return_picking.action_confirm()
                for move in return_picking.move_ids:
                    move.quantity_done = move.product_uom_qty
                return_picking.button_validate()
            elif self.second_picking_id.state not in ['cancel', 'done']:
                self.second_picking_id.action_cancel()

        # Update DHS state to 'cancel'
        self.state = 'cancel'
    
    def action_gate_out(self):
        product_lines = self.donation_home_service_line_ids.filtered(
            lambda l: l.product_id.detailed_type != 'service'
        )

        if product_lines:
            self.picking_id.action_confirm()
            self.picking_id.action_assign()
            self.picking_id.button_validate()
        else:
            self.state = 'gate_in'

    
    def action_gate_in(self):
        self.second_picking_id.action_confirm()
        self.second_picking_id.action_assign()
        self.second_picking_id.button_validate()
        
        self.state = 'gate_in'
    
    def action_show_picking(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Gate Out',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.picking_id.id,
            'target': 'current',
        }

    @api.model
    def create_dhs_record(self, data):
        product_lines = []

        for line in data['order_lines']:
            # Assuming 'product_id' is a valid product ID
            product_lines.append((0, 0, {
                'product_id': line['product_id'],
                'quantity': line['quantity'],
            }))
        
        dhs = self.env['donation.home.service'].create({
            'donor_id': data['donor_id'],
            'address': data['address'],
            'service_charges': data['service_charges'],
            'donation_home_service_line_ids': product_lines
        })

        for line in dhs.donation_home_service_line_ids:
            base_price = line.product_id.lst_price
            taxes = line.product_id.taxes_id

            total_price_incl_tax = base_price

            for tax in taxes:
                if tax.amount_type == 'percent':
                    tax_amount = base_price * (tax.amount / 100)

                    total_price_incl_tax += tax_amount
                else:
                    total_price_incl_tax += tax.amount

            line.amount = total_price_incl_tax * line.quantity

        dhs.calculate_amount()
        dhs.calculate_service_charges()
        dhs.action_confirm()
       
        return{
            "status": "success",
            "id": dhs.id
        }
    
    @api.model
    def get_dhs_record(self, data):
        """Fetch DHS record by name and return product information"""
        # Search for the DHS record
        dhs = self.sudo().search([('name', '=', data['name']), ('state', '!=', 'paid')], limit=1)
        
        if not dhs:
            return {
                "status": "error",
                "body": f"Donation Home Service record with reference {data['name']} not found."
            }
        
        if dhs.state not in ['gate_pass', 'gate_in']:
            return {
                "status": "error",
                "body": f"Current status of {data['name']} is in a {dhs.state.capitalize()}."
            }
        
        # Prepare product data for POS
        products_data = []
        
        # Add regular product lines
        for line in dhs.donation_home_service_line_ids:
            product = line.product_id
            products_data.append({
                'product_id': product.id,
                'name': product.name,
                'quantity': line.quantity,
                'price': product.lst_price,
                'default_code': product.default_code,
                'category': product.categ_id.name if product.categ_id else ''
            })
        
        # Add delivery charges if applicable
        service_charges = getattr(dhs, 'service_charges', 0.0)
        
        if service_charges and float(service_charges) > 0:
            service_product = self.env['product.product'].search([
                ('name', '=', 'Service Charges'),
                ('type', '=', 'service'),
                ('available_in_pos', '=', True)
            ], limit=1)
            
            if service_product:
                products_data.append({
                    'product_id': service_product.id,
                    'name': service_product.name,
                    'quantity': 1,
                    'price': float(service_charges),
                    'default_code': service_product.default_code or 'DELIVERY',
                    'category': service_product.categ_id.name if service_product.categ_id else 'Services',
                    'is_delivery_charge': True
                })
        
        return {
            'id': dhs.id,
            'name': dhs.name,
            'donor_id': dhs.donor_id.id if dhs.donor_id else False,
            'donor_name': dhs.donor_id.name if dhs.donor_id else '',
            'service_charges': float(service_charges),
            'products': products_data,
            'success': True
        }