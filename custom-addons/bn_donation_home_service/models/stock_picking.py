from odoo import models, fields, _
from odoo.exceptions import ValidationError


class StockPicking(models.Model):
    _inherit = 'stock.picking'


    check_picking = fields.Boolean('Check Picking', default=False)

    dhs_id = fields.Many2one('donation.home.service', 'Donation Home Service')


    def button_validate(self):
        # Check if this is a donation home service picking (original)
        if self.dhs_id and not self.check_picking:
            try:
                # Create a gate in picking
                picking = self.create({
                    'partner_id': self.partner_id.id,
                    'picking_type_id': self.env.ref('bn_donation_home_service.donation_home_service_in_stock_picking_type').id,
                    'origin': self.name,
                    'dhs_id': self.dhs_id.id,
                    'state' : 'draft',
                })

                for line in self.dhs_id.donation_home_service_line_ids:
                    if line.product_id.detailed_type == 'product':
                        self.env['stock.move'].create({
                            'name': f'Gate In against {self.dhs_id.name}',
                            'product_id': line.product_id.id,
                            'product_uom': line.product_id.uom_id.id,
                            'product_uom_qty': line.quantity,
                            'location_id': self.env.ref('bn_donation_home_service.gate_out_location').id,
                            'location_dest_id': self.env.ref('bn_donation_home_service.gate_in_location').id,
                            'state': 'draft',
                            'picking_id': picking.id
                        })

                for move in picking.move_ids:   
                    move._action_assign()
                
                # Update home donation service state from 'pending' to 'gatepass'
                if self.dhs_id:
                    self.dhs_id.state = 'gate_out'
                    self.dhs_id.second_picking_id = picking.id
                
                # Validate the original picking
                super(StockPicking, self).button_validate()
                
                # Return action to show the duplicate picking
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Return Picking Created'),
                    'res_model': 'stock.picking',
                    'res_id': picking.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
                
            except Exception as e:
                raise ValidationError(_('Error creating return picking: %s') % str(e))
        # Handle check_picking validation (duplicate picking)
        elif self.check_picking and self.dhs_id:
            return self._validate_check_picking()
        else:
            # Normal validation for non-donation pickings
            return super(StockPicking, self).button_validate()

    def _validate_check_picking(self):
        """Handle validation for check picking (duplicate with swapped locations)"""
        try:
            # First, validate the picking normally
            result = super(StockPicking, self).button_validate()
            
            # Create live_stock.requisition record
            # self._create_live_stock_slaughter_cutting()
            
            # Update home donation service state from 'gatepass' to 'gatein'
            if self.dhs_id:
               if self.dhs_id.state =='gate_out':
                    self.dhs_id.state = 'gate_in'
                
            return result  
        except Exception as e:
            raise ValidationError(_('Error validating check picking: %s') % str(e))

    def _create_live_stock_slaughter_cutting(self):
        """Create live_stock_slaughter.cutting record based on the picking"""
        for move in self.move_ids:
            product = move.product_id
            # raise UserError(str(move.product_id.read()))
            if product and product.detailed_type == 'product':
                # Get the product template
                product_template = product.product_tmpl_id

                # Create live stock slaughter cutting record
                cutting_vals = {
                    'product': product_template.id,
                    'quantity': move.quantity,
                    'price': product.lst_price or 0.0,  # Using list price
                    'product_code': product.default_code ,
                    'origin': self.origin if self.origin else self.origin.replace('Gate In against ', ''),
                    
                }
                
                self.env['live_stock_slaughter.live_stock_slaughter'].create(cutting_vals)