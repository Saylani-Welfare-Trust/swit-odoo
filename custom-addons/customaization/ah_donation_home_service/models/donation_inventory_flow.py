# from odoo import fields,api,models,_
# from odoo import models, fields, api, _
# from odoo.exceptions import UserError

# class StockPicking(models.Model):
#     _inherit = 'stock.picking'


#     check_picking = fields.Boolean(string='Check Picking', default=False)

#     def button_validate(self):
#         # raise UserError(str(self.read()))
#         # Check if this is a donation home service picking (original)
#         if self.dhs_id and self.is_donation_home_service and not self.check_picking:
#             try:
#                 # Create duplicate picking with swapped locations
#                 duplicate_picking = self.copy({
#                     'name': self.env['ir.sequence'].next_by_code('stock.picking') or _('New'),
#                     'origin': f"Return for {self.origin}",
#                     'state': 'draft',
#                     'move_ids': [],
#                     'dhs_id': self.dhs_id.id,
#                     'check_picking': True,  # Mark as check picking
#                 })
                
#                 # Create duplicate moves with swapped locations
#                 for move in self.move_ids:
#                     # Create duplicate move with swapped locations
#                     duplicate_move = move.copy({
#                         'picking_id': duplicate_picking.id,
                       
#                         'state': 'draft',
#                         'move_line_ids': [],
#                     })
                    
#                     duplicate_move.location_id = move.location_dest_id,
#                     duplicate_move.location_dest_id =  move.location_id,
#                     # raise UserError(str(duplicate_move. location_id)+"location_id "+ " dest_id  "+str(duplicate_move. location_dest_id))
                    
#                     # Copy move lines with swapped locations
#                     for move_line in move.move_line_ids:
#                         move_line_vals = {
#                             'move_id': duplicate_move.id,
#                             'picking_id': duplicate_picking.id,
#                             'product_uom_id': move_line.product_uom_id.id,
#                             'product_id': move_line.product_id.id,
#                             'quantity': move_line.quantity,
#                         }
                        
#                         # Optional fields
#                         optional_fields = ['lot_id', 'package_id', 'result_package_id', 'owner_id', 'lot_name']
#                         for field in optional_fields:
#                             if move_line[field]:
#                                 move_line_vals[field] = move_line[field].id if hasattr(move_line[field], 'id') else move_line[field]
                        
#                         self.env['stock.move.line'].create(move_line_vals)

                
                
                
#                 # Validate the original picking
#                 result = super(StockPicking, self).button_validate()
                
#                 # Update home donation service state from 'pending' to 'gatepass'
#                 if self.dhs_id:
#                     self.dhs_id.write({'state': 'gat_pass'})


#                 gate_in = self.env.ref('__custom__.gate___in', False)

#                 duplicate_picking_location = duplicate_picking.location_id

#                 duplicate_picking.location_id = duplicate_picking.location_dest_id,

#                 duplicate_picking.location_dest_id, =  gate_in,

#                 # raise UserError(str(duplicate_picking.read()))

                
#                 # Return action to show the duplicate picking
#                 return {
#                     'type': 'ir.actions.act_window',
#                     'name': _('Return Picking Created'),
#                     'res_model': 'stock.picking',
#                     'res_id': duplicate_picking.id,
#                     'view_mode': 'form',
#                     'target': 'current',
#                     'context': {'create': False},
#                 }
                
#             except Exception as e:
#                 raise UserError(_('Error creating return picking: %s') % str(e))
        
#         # Handle check_picking validation (duplicate picking)
#         elif self.check_picking and self.dhs_id:
#             return self._validate_check_picking()
        
#         else:
#             # Normal validation for non-donation pickings
#             return super(StockPicking, self).button_validate()

#     def _validate_check_picking(self):
#         """Handle validation for check picking (duplicate with swapped locations)"""
#         try:
#             # First, validate the picking normally
#             result = super(StockPicking, self).button_validate()
            
#             # Create live_stock.requisition record
#             self._create_live_stock_slaughter_cutting()
            
#             # Update home donation service state from 'gatepass' to 'gatein'
#             if self.dhs_id:
#                if self.dhs_id.state =='gat_pass':
            
#                     self.dhs_id.write({'state': 'gat_in'})
                
#             return result
            
#         except Exception as e:
#             raise UserError(_('Error validating check picking: %s') % str(e))

#     def _create_live_stock_slaughter_cutting(self):

#         original_picking = self.env['stock.picking'].search([
#             ('dhs_id', '=', self.dhs_id.id),
#             ('is_donation_home_service', '=', True),
#             ('check_picking', '=', False)
#         ], limit=1)
#         """Create live_stock_slaughter.cutting record based on the picking"""
#         for move in self.move_ids:
#             product = move.product_id
#             # raise UserError(str(move.product_id.read()))
#             if product and product.detailed_type == 'product':
#                 # Get the product template
#                 product_template = product.product_tmpl_id
                

            
#                 # Create live stock slaughter cutting record
#                 cutting_vals = {
#                     # 'company_id': self.company_id.id,
#                     'product': product_template.id,
#                     'quantity': move.quantity,
#                     'price': product.lst_price or 0.0,  # Using list price
#                     'product_code': product.default_code ,
#                     'origin': original_picking.origin if original_picking else self.origin.replace('Return for ', ''),
                    
#                 }
#                 # raise UserError(str(cutting_vals))
                
#                 self.env['live_stock_slaughter.live_stock_slaughter'].create(cutting_vals)
                

from odoo import fields,api,models,_
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class StockPicking(models.Model):
    _inherit = 'stock.picking'


    check_picking = fields.Boolean(string='Check Picking', default=False)

    def button_validate(self):
        # raise UserError(str(self.read()))
        # Check if this is a donation home service picking (original)
        if self.dhs_id and self.is_donation_home_service and not self.check_picking:
            try:
                # Create duplicate picking with swapped locations
                duplicate_picking = self.copy({
                    'name': self.env['ir.sequence'].next_by_code('stock.picking') or _('New'),
                    'origin': f"Return for {self.origin}",
                    'state': 'draft',
                    'move_ids': [],
                    'dhs_id': self.dhs_id.id,
                    'check_picking': True,  # Mark as check picking
                })
                
                # Create duplicate moves with swapped locations
                for move in self.move_ids:
                    # Create duplicate move with swapped locations
                    duplicate_move = move.copy({
                        'picking_id': duplicate_picking.id,
                       
                        'state': 'draft',
                        'move_line_ids': [],
                    })
                    duplicate_move.location_id = move.location_dest_id,
                    duplicate_move.location_dest_id =  move.location_id,
                    # raise UserError(str(duplicate_move. location_id)+"location_id "+ " dest_id  "+str(duplicate_move. location_dest_id))
                    
                    # Copy move lines with swapped locations
                    for move_line in move.move_line_ids:
                        move_line_vals = {
                            'move_id': duplicate_move.id,
                            'picking_id': duplicate_picking.id,
                            'product_uom_id': move_line.product_uom_id.id,
                            'product_id': move_line.product_id.id,
                            'quantity': move_line.quantity,
                        }
                        
                        # Optional fields
                        optional_fields = ['lot_id', 'package_id', 'result_package_id', 'owner_id', 'lot_name']
                        for field in optional_fields:
                            if move_line[field]:
                                move_line_vals[field] = move_line[field].id if hasattr(move_line[field], 'id') else move_line[field]
                        
                        self.env['stock.move.line'].create(move_line_vals)

                
                
                
                # Validate the original picking
                result = super(StockPicking, self).button_validate()
                
                # Update home donation service state from 'pending' to 'gatepass'
                if self.dhs_id:
                    self.dhs_id.write({'state': 'gat_pass'})
                duplicate_picking_location = duplicate_picking.location_id

                duplicate_picking.location_id = duplicate_picking.location_dest_id,

                duplicate_picking.location_dest_id, =  duplicate_picking_location,

                # raise UserError(str(duplicate_picking.read()))

                
                # Return action to show the duplicate picking
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Return Picking Created'),
                    'res_model': 'stock.picking',
                    'res_id': duplicate_picking.id,
                    'view_mode': 'form',
                    'target': 'current',
                    'context': {'create': False},
                }
                
            except Exception as e:
                raise UserError(_('Error creating return picking: %s') % str(e))
        
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
            self._create_live_stock_slaughter_cutting()
            
            # Update home donation service state from 'gatepass' to 'gatein'
            if self.dhs_id:
               if self.dhs_id.state =='gat_pass':
            
                    self.dhs_id.write({'state': 'gat_in'})
                
            return result
            
        except Exception as e:
            raise UserError(_('Error validating check picking: %s') % str(e))

    def _create_live_stock_slaughter_cutting(self):

        original_picking = self.env['stock.picking'].search([
            ('dhs_id', '=', self.dhs_id.id),
            ('is_donation_home_service', '=', True),
            ('check_picking', '=', False)
        ], limit=1)
        """Create live_stock_slaughter.cutting record based on the picking"""
        for move in self.move_ids:
            product = move.product_id
            # raise UserError(str(move.product_id.read()))
            if product and product.detailed_type == 'product':
                # Get the product template
                product_template = product.product_tmpl_id
                

            
                # Create live stock slaughter cutting record
                cutting_vals = {
                    # 'company_id': self.company_id.id,
                    'product': product_template.id,
                    'quantity': move.quantity,
                    'price': product.lst_price or 0.0,  # Using list price
                    'product_code': product.default_code ,
                    'origin': original_picking.origin if original_picking else self.origin.replace('Return for ', ''),
                    
                }
                # raise UserError(str(cutting_vals))
                
                self.env['live_stock_slaughter.live_stock_slaughter'].create(cutting_vals)
                











