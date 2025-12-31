import pprint
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


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
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Donation Home Service"


    donor_id = fields.Many2one('res.partner', string="Donor")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)
    picking_id = fields.Many2one('stock.picking', string="Stock Picking")
    second_picking_id = fields.Many2one('stock.picking', string="Stock Picking")
    country_code_id = fields.Many2one(related='donor_id.country_code_id', string="Country Code", store=True)
    # direct_deposit_id = fields.Many2one('direct.deposit', string="Direct Deposit")

    name = fields.Char('Name', default="New")
    mobile = fields.Char(related='donor_id.mobile', string="Mobile No.", size=10)

    address = fields.Text('Address')

    state = fields.Selection(selection=status_selection, string="Status", default="draft")

    amount = fields.Monetary('Amount', currency_field='currency_id')
    total_amount = fields.Monetary('Total Amount', currency_field='currency_id')
    service_charges = fields.Monetary('Service Charges', currency_field='currency_id')

    tag_number = fields.Char('Tag Number')

    donation_home_service_line_ids = fields.One2many('donation.home.service.line', 'donation_home_service_id', string="Donation Home Service Lines")


    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('donation_home_service') or ('New')

        return super(DonationHomeService, self).create(vals)
    
    def calculate_amount(self):
        self.amount = sum(line.amount for line in self.donation_home_service_line_ids)

    def calculate_service_charges(self):
        self.total_amount = self.amount + self.service_charges
    
    def action_cancel(self):
        def _create_return_for_picking(picking):
            ReturnWizard = self.env['stock.return.picking']

            wizard = ReturnWizard.with_context(
                active_id=picking.id,
                active_ids=[picking.id],
            ).create({'picking_id': picking.id})

            # Encode quantities (THIS SATISFIES VALIDATION)
            for line in wizard.product_return_moves:
                line.quantity = line.move_id.product_uom_qty

            # _create_returns() returns (action, picking_id) - picking_id is a single int, not a list
            action_result = wizard._create_returns()
            # Get the return picking ID from the action result
            if isinstance(action_result, tuple):
                return_picking_id = action_result[0]
            else:
                # In some versions, it might return an action dict
                return_picking_id = action_result.get('res_id')
            
            # raise UserError(pprint.pformat(return_picking_id))
            return_picking = self.env['stock.picking'].browse(return_picking_id)
            
            return_picking.action_confirm()
            
            # Only assign if there are moves to assign
            if return_picking.move_ids:
                try:
                    return_picking.action_assign()
                except Exception:
                    pass  # Continue even if assignment fails
            
            # Set quantities on move lines for validation
            for move in return_picking.move_ids:
                move.quantity = move.product_uom_qty

            return_picking.button_validate()

        for picking in [self.picking_id, self.second_picking_id]:
            if picking:
                if picking.state == 'done':
                    _create_return_for_picking(picking)
                elif picking.state not in ['cancel', 'done']:
                    picking.action_cancel()

        self.state = 'cancel'


    
    def action_gate_out(self):
        """Confirm donation and create stock picking if stockable product lines exist."""
        StockPicking = self.env['stock.picking']
        StockMove = self.env['stock.move']
        StockLocation = self.env.ref('stock.stock_location_stock')
        GateOutLocation = self.env.ref('bn_donation_home_service.gate_out_location')
        PickingType = self.env.ref('bn_donation_home_service.donation_home_service_out_stock_picking_type')

        for record in self:

            # tag number is mandatory
            if not record.tag_number:
                raise ValidationError("Tag Number is required before proceeding.")

            # Skip if picking already exists
            if record.picking_id:
                continue

            # Only NON-service product lines
            stockable_lines = record.donation_home_service_line_ids.filtered(
                lambda l: l.product_id.detailed_type not in ['service', 'consu'] and l.product_id.type == 'product'
            )

            # If NO stockable products → do NOT create picking
            if not stockable_lines:
                record.state = 'gate_out'   # or 'paid' if you prefer
                continue

            # -----------------------------------------
            # Create Picking
            # -----------------------------------------
            picking = StockPicking.create({
                'partner_id': record.donor_id.id,
                'picking_type_id': PickingType.id,
                'origin': record.name,
                'dhs_id': record.id,
                'state': 'draft',
            })

            # -----------------------------------------
            # Create Moves for Stockable Products Only
            # -----------------------------------------
            moves_vals = [{
                'name': f'Gate Out against {record.name}',
                'product_id': line.product_id.id,
                'product_uom': line.product_id.uom_id.id,
                'product_uom_qty': line.quantity,
                'location_id': StockLocation.id,
                'location_dest_id': GateOutLocation.id,
                'picking_id': picking.id,
                'state': 'draft',
            } for line in stockable_lines]

            StockMove.create(moves_vals)

            # -----------------------------------------
            # Confirm & Validate Picking
            # -----------------------------------------
            picking.action_confirm()
            picking.action_assign()

            for move in picking.move_ids:
                move.quantity = move.product_uom_qty

            picking.button_validate()

            # -----------------------------------------
            # Link Picking
            # -----------------------------------------
            record.picking_id = picking.id

            if not picking.dhs_id:
                picking.dhs_id = record.id

            record.state = 'gate_out'
    
    def action_gate_in(self):
        """Confirm donation and create stock picking if stockable product lines exist."""
        StockPicking = self.env['stock.picking']
        StockMove = self.env['stock.move']
        StockLocation = self.env.ref('bn_donation_home_service.gate_out_location')
        GateOutLocation = self.env.ref('bn_donation_home_service.gate_in_location')
        PickingType = self.env.ref('bn_donation_home_service.donation_home_service_in_stock_picking_type')

        for record in self:

            # Skip if picking already exists
            if record.second_picking_id:
                continue

            # Only NON-service product lines
            stockable_lines = record.donation_home_service_line_ids.filtered(
                lambda l: l.product_id.detailed_type not in ['service', 'consu'] and l.product_id.type == 'product'
            )

            # If NO stockable products → do NOT create picking
            if not stockable_lines:
                record.state = 'gate_out'   # or 'paid' if you prefer
                continue

            # -----------------------------------------
            # Create Picking
            # -----------------------------------------
            picking = StockPicking.create({
                'partner_id': record.donor_id.id,
                'picking_type_id': PickingType.id,
                'origin': record.name,
                'dhs_id': record.id,
                'state': 'draft',
            })

            # -----------------------------------------
            # Create Moves for Stockable Products Only
            # -----------------------------------------
            moves_vals = [{
                'name': f'Gate Out against {record.name}',
                'product_id': line.product_id.id,
                'product_uom': line.product_id.uom_id.id,
                'product_uom_qty': line.quantity,
                'location_id': StockLocation.id,
                'location_dest_id': GateOutLocation.id,
                'picking_id': picking.id,
                'state': 'draft',
            } for line in stockable_lines]

            StockMove.create(moves_vals)

            # -----------------------------------------
            # Confirm & Validate Picking
            # -----------------------------------------
            picking.action_confirm()
            picking.action_assign()

            for move in picking.move_ids:
                move.quantity = move.product_uom_qty

            picking.button_validate()

            # -----------------------------------------
            # Link Picking
            # -----------------------------------------
            record.second_picking_id = picking.id

            if not picking.dhs_id:
                picking.dhs_id = record.id

            record.state = 'gate_in'
    
    def action_show_picking(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Gate Out',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.picking_id.id,
            'target': 'current',
        }
    
    def action_show_second_picking(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Gate Out',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.second_picking_id.id,
            'target': 'current',
        }

    @api.model
    def create_dhs_record(self, data):
        # raise UserError(str(data))

        # -------------------------
        # 1. Prepare Line Items
        # -------------------------
        product_lines = []
        for line in data['order_lines']:
            product_lines.append((0, 0, {
                'product_id': line['product_id'],
                'quantity': line['quantity'],
                'amount': line['price'],
                'remarks': line['remarks'] if line.get('remarks') else '',
            }))

        # -------------------------
        # 2. Create DHS Record
        # -------------------------
        dhs = self.env['donation.home.service'].create({
            'donor_id': data['donor_id'],
            'address': data['address'],
            'service_charges': data['service_charges'],
            'donation_home_service_line_ids': product_lines,
        })

        # -------------------------
        # 3. Check if ALL lines are service products
        # -------------------------
        all_service = all(
            line.product_id.detailed_type == 'service'
            for line in dhs.donation_home_service_line_ids
        )

        if all_service:
            dhs.state = 'gate_in'     # ✔ only if 100% service lines

        # -------------------------
        # 4. Calculate prices & taxes for all lines
        # -------------------------
        for line in dhs.donation_home_service_line_ids:
            base_price = line.product_id.lst_price
            taxes = line.product_id.taxes_id

            total_price_incl_tax = base_price
            for tax in taxes:
                if tax.amount_type == 'percent':
                    total_price_incl_tax += base_price * (tax.amount / 100)
                else:
                    total_price_incl_tax += tax.amount

            if not line.amount:
                line.amount = total_price_incl_tax * line.quantity

        # -------------------------
        # 5. Recalculate totals
        # -------------------------
        dhs.calculate_amount()
        dhs.calculate_service_charges()

        return {
            "status": "success",
            "id": dhs.id,
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
                ('name', '=', 'Donation Home Service Charges'),
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