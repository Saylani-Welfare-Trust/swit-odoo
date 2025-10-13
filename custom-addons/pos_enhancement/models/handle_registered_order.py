from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class HandleRegisteredOrder(models.TransientModel):
    _name = 'handle.registered.order'
    
    barcode=fields.Char(string="Barcode")
    
    def process_barcode(self):
        self.ensure_one()
        register_order=self.env['pos.registered.order'].search([('barcode', '=', self.barcode)],limit=1)
        
        company = self.env.user.company_id 
        donation_journal=self.env['account.journal'].search([('name','=','Donation Journal'),('type','=','general')],limit=1)
        if not donation_journal:
            raise UserError("Donation Journal not found")
        # raise UserError(str(donation_journal))
        if register_order.is_applicable():
            if register_order.disbursement_type == 'in_kind':
                if not self.env.user.has_group('stock.group_stock_user'):
                    raise ValidationError('Invalid Operation (In Kind)')

                picking_vals = {
                    'partner_id': register_order.partner_id.id,  
                    'picking_type_id': 2,
                    'company_id': company.id, 
                    'pos_register_order_id': register_order.id,
                    # 'donation_journal_entry_id': donation_journal_entry.id,
                    'move_ids': [(0, 0, {
                        'name': line.product_id.name,
                        'product_id': line.product_id.id,
                        'product_uom_qty': line.qty,
                        'location_id': 8,
                        'location_dest_id': 5,
                        'state': 'draft',
                    }) for line in register_order.order_lines] 
                }
                new_picking = self.env['stock.picking'].create(picking_vals)
                
                # raise UserError(str(donation_journal_entry))
                
                register_order.order_validate(new_picking.name,new_picking)
                return {
                    'name': 'New Delivery',
                    'type': 'ir.actions.act_window',
                    'view_mode': 'form',
                    'res_model': 'stock.picking',
                    'res_id': new_picking.id,
                }
            elif register_order.disbursement_type == 'cash':
                if not self.env.user.has_group('account.group_account_user'):
                    raise ValidationError('Invalid Operation (Cash)')

                out_invoice_values={
                    'partner_id': register_order.partner_id.id,
                    'move_type': 'entry',
                    'company_id': company.id,
                    'journal_id': donation_journal.id,
                    'pos_register_order_id': register_order.id,
                    'line_ids':[(0,0,{'account_id':line.product_id.product_entry_line[0].for_debit.id,'name':line.product_id.name,'debit':line.price_subtotal,'display_type':'product'}) for line in register_order.order_lines] + [
                        (0,0,{"account_id":donation_journal.default_account_id.id,"credit":sum(register_order.order_lines.mapped('price_subtotal')),"display_type":'product'})]
                }
                donation_journal_entry=self.env['account.move'].create(out_invoice_values)               
                # donation_journal_entry=self.env['account.move'].create(donation_journal_entry_values)               
                
                # out_invoice_values={
                #     'partner_id': register_order.partner_id.id,
                #     'move_type': 'in_invoice',
                #     'company_id': company.id,
                #     'pos_register_order_id': register_order.id,
                #     'invoice_line_ids': [(0,0,{
                #         'product_id': line.product_id.id,
                #         'quantity': line.qty,
                #         'price_unit': line.price_unit,
                #         'name': line.product_id.name,
                #     }) for line in register_order.order_lines]
                # }
                # new_invoice=self.env['account.move'].create(out_invoice_values)
                register_order.order_validate(donation_journal_entry.name,donation_journal_entry)
                # raise UserError(str(new_invoice))
                return {
                    'name': 'New Invoice',
                    'type': 'ir.actions.act_window',
                    'view_mode': 'form',
                    'res_model': 'account.move',
                    'res_id': donation_journal_entry.id,
                }
        else:
            raise UserError(_('Barcode is not applicable'))