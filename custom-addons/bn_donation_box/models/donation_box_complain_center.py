from odoo import fields, models, api
from odoo.exceptions import ValidationError,UserError


box_status_selection = [
    ('missing', 'Missing'),
    ('broken', 'Broken'),
    ('robbery', 'Robbery'),
    ('return', 'Return'),
    ('repaired', 'Repaired'),
]

status_selection = [
    ('draft', 'Draft'),
    ('process', 'Process'),
    ('resolved', 'Resolved'),
]


class DonationBoxComplain(models.Model):
    _name = 'donation.box.complain.center'
    _description = 'Donation Box Complain Center'
    _inherit = ["mail.thread", "mail.activity.mixin"]


    lot_id = fields.Many2one('stock.lot', string="Lot", tracking=True)
    rider_id = fields.Many2one('hr.employee', string="Rider", tracking=True)
    donation_box_registration_installation_id = fields.Many2one('donation.box.registration.installation', string="Donation Box", compute="_set_registration_id", tracking=True)
    stored_registration_id = fields.Many2one('donation.box.registration.installation', string="Stored Registration", tracking=True)
    return_picking_id = fields.Many2one('stock.picking', string="Return", tracking=True)
    scrap_picking_id = fields.Many2one('stock.scrap', string="Scrap", tracking=True)
    scrap_return_picking_id = fields.Many2one('stock.picking', string="Scrap Return Picking", tracking=True)

    employee_category_id = fields.Many2one('hr.employee.category', string="Employee Category", default=lambda self: self.env.ref('bn_donation_box.donation_box_rider_hr_employee_category', raise_if_not_found=False).id)
    
    name = fields.Char(related='donation_box_registration_installation_id.name', string='Registration / Installation No.', store=True, tracking=True)
    shop_name = fields.Char(related='donation_box_registration_installation_id.shop_name', string='Shop Name', store=True, tracking=True)
    contact_no = fields.Char(related='donation_box_registration_installation_id.contact_no', string='Contact No', store=True, tracking=True)
    location = fields.Char(related='donation_box_registration_installation_id.location', string='Requested Location', store=True, tracking=True)
    contact_person = fields.Char(related='donation_box_registration_installation_id.contact_person', string='Contact Person', store=True, tracking=True)

    status = fields.Selection(selection=status_selection, string='Status', default='draft', tracking=True)
    box_status = fields.Selection(selection=box_status_selection, string="Box Status", tracking=True)

    installer_id = fields.Many2one(related='donation_box_registration_installation_id.installer_id', string="Installer")
    zone_id = fields.Many2one(related='donation_box_registration_installation_id.zone_id', string="Zone", store=True, tracking=True)
    city_id = fields.Many2one(related='donation_box_registration_installation_id.city_id', string="City", store=True, tracking=True)
    donor_id = fields.Many2one(related='donation_box_registration_installation_id.donor_id', string="Donor", store=True, tracking=True)
    sub_zone_id = fields.Many2one(related='donation_box_registration_installation_id.sub_zone_id', string="Sub Zone", store=True, tracking=True)
    product_id = fields.Many2one(related='donation_box_registration_installation_id.product_id', string="Donation Box Category", store=True, tracking=True)
    donation_box_request_id = fields.Many2one(related='donation_box_registration_installation_id.donation_box_request_id', string="Donation Box Request", store=True)
    installation_category_id = fields.Many2one(related='donation_box_registration_installation_id.installation_category_id', string="Installation Category", store=True, tracking=True)

    installation_date = fields.Date(related='donation_box_registration_installation_id.installation_date', string='Installation Date', store=True, tracking=True)

    remarks = fields.Text('Remarks', tracking=True)


    def action_process(self):
        # Store the registration ID before it gets closed during resolve
        if self.donation_box_registration_installation_id:
            self.stored_registration_id = self.donation_box_registration_installation_id.id

        if self.box_status == 'repaired':
            raise ValidationError("Please contact your firendly administrator as you cannot set box status directly to 'Repaired'.")
        
        self.status = 'process'
    
    def action_resolve(self):
        # Use stored_registration_id as it persists after resolve
        registration = self.stored_registration_id or self.donation_box_registration_installation_id
        
        if self.box_status != 'return':
            if registration:
                registration.status = 'close'
            self.lot_id.is_not_return = True

            self.env['key'].search([('lot_id', '=', self.lot_id.id)]).unlink()

        if self.box_status == 'broken':
            self.action_scrap()

        self.status = 'resolved'

    @api.depends('lot_id')
    def _set_registration_id(self):
        for rec in self:
            rec.donation_box_registration_installation_id = None

            if rec.lot_id:
                rec.donation_box_registration_installation_id = self.env['donation.box.registration.installation'].search([('lot_id', '=', rec.lot_id.id), ('status', '=', 'available')], order='id desc', limit=1).id

    def action_return(self):
        """Return ONLY the selected serial (lot) from a multi-line picking."""
        for rec in self:

            if not rec.lot_id:
                raise ValidationError("Please select a Serial (Lot) to return.")

            registration = rec.stored_registration_id or rec.donation_box_registration_installation_id
            if not registration:
                raise ValidationError("No installation record found for this serial.")

            # 1️⃣ Find original picking
            picking = registration.donation_box_request_id.picking_id
            if not picking or picking.state != "done":
                picking = self.env['stock.picking'].search([
                    ('origin', '=', registration.donation_box_request_id.name),
                    ('state', '=', 'done')
                ], order="id desc", limit=1)

            if not picking:
                raise ValidationError("No completed Stock Picking found for this box.")

            # 2️⃣ Find the exact move line for this serial
            original_ml = picking.move_line_ids.filtered(
                lambda ml: ml.lot_id.id == rec.lot_id.id
            )

            if not original_ml:
                raise ValidationError("This serial does not belong to the selected picking.")

            original_ml = original_ml[0]
            product = original_ml.product_id

            # 3️⃣ Create return wizard
            return_wizard = self.env['stock.return.picking'].create({
                'picking_id': picking.id,
            })

            # 4️⃣ Return ONLY this product
            for line in return_wizard.product_return_moves:
                line.quantity = 1 if line.product_id.id == product.id else 0

            # 5️⃣ Create return picking
            res = return_wizard.create_returns()
            return_picking = self.env['stock.picking'].browse(res['res_id'])

            # 6️⃣ KEEP ONLY the move of selected product
            return_move = return_picking.move_ids_without_package.filtered(
                lambda m: m.product_id.id == product.id
            )

            if not return_move:
                raise ValidationError("Return move not generated.")

            # Delete other product moves completely
            (return_picking.move_ids_without_package - return_move).unlink()

            # 7️⃣ Fix move line (SERIAL SAFE)
            return_ml = return_move.move_line_ids[:1]

            # Remove extra move lines
            (return_move.move_line_ids - return_ml).unlink()

            return_ml.write({
                'lot_id': rec.lot_id.id,
                'quantity': 1,
            })

            # 8️⃣ Validate return picking
            return_picking.button_validate()

            # 9️⃣ Close installation & complaint
            registration.status = 'close'
            rec.status = 'resolved'
            rec.return_picking_id = return_picking.id

            self.env['key'].search([('lot_id', '=', self.lot_id.id)]).unlink()

            # 🔟 Reset lot flags
            rec.lot_id.write({
                'lot_consume': False,
                'location_id': self.donation_box_request_id.source_location_id.id,
                'is_not_return': False,
            })

    def action_scrap(self):
        """Scrap the selected serial (lot) instead of returning picking."""
        for rec in self:

            if not rec.lot_id:
                raise ValidationError("Please select a Serial (Lot) to scrap.")

            registration = rec.stored_registration_id or rec.donation_box_registration_installation_id
            if not registration:
                raise ValidationError("No installation record found for this serial.")

            # 1. Find original picking (delivery)
            picking = registration.donation_box_request_id.picking_id

            if not picking or picking.state != "done":
                picking = self.env['stock.picking'].search([
                    ('origin', '=', registration.donation_box_request_id.name),
                    ('state', '=', 'done')
                ], order="id desc", limit=1)

            if not picking:
                raise ValidationError("No completed Stock Picking found for this box.")

            # 2. Find move line for the selected serial
            serial_used = picking.move_line_ids.filtered(
                lambda ml: ml.lot_id.id == rec.lot_id.id
            )

            if not serial_used:
                raise ValidationError("This serial does not belong to the selected picking.")

            product = serial_used.product_id

            # 3. Determine scrap location
            scrap_location = self.env['stock.location'].search([
                ('scrap_location', '=', True),
            ], limit=1)
            if not scrap_location:
                raise ValidationError("Scrap location not configured in the system.")

            # 4. Create Scrap Record
            scrap = self.env["stock.scrap"].create({
                "product_id": product.id,
                "lot_id": rec.lot_id.id,
                "scrap_qty": 1,
                "product_uom_id": serial_used.product_uom_id.id,
                "location_id": picking.location_dest_id.id,   # From where it will be scrapped
                "scrap_location_id": scrap_location.id,       # To scrap location
                "company_id": picking.company_id.id,
                "origin": picking.name,
            })

            # 5. Confirm / Validate the scrap
            scrap.action_validate()

            # 7. Close complain
            rec.status = "resolved"
            rec.scrap_picking_id = scrap.id

    def action_return_picking(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.return_picking_id.id,
            'target': 'current'
        }
    
    def action_scrap_picking(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.scrap',
            'view_mode': 'form',
            'res_id': self.scrap_picking_id.id,
            'target': 'current'
        }

    def action_scrap_return_move(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.scrap_return_picking_id.id,
            'target': 'current'
        }

    def action_repair(self):
        """
        Repair broken donation boxes (single or bulk).
        Once repaired, the box becomes available in stock for re-allocation and installation.
        """
        broken_records = self.filtered(lambda r: r.box_status in ['broken', 'repaired'])
        
        if not broken_records:
            raise ValidationError("No broken boxes selected for repair. Only boxes with 'Broken' or 'Repaired' status can be repaired.")

        for rec in broken_records:
            # 1. Change box status to 'repaired'
            rec.box_status = 'repaired'
            
            # 2. Make the lot available again for re-allocation
            if rec.lot_id:
                # Reset lot flags so it becomes available in stock
                rec.lot_id.lot_consume = False
                rec.lot_id.is_not_return = False
            
            # 3. If there's a scrap record, we need to reverse the scrap
            # by creating an internal transfer from scrap location back to stock
            if rec.scrap_picking_id:
                scrap_record = rec.scrap_picking_id

                # Get the warehouse's stock location (lot_stock_id)
                warehouse = self.env['stock.warehouse'].search([
                    ('company_id', '=', scrap_record.company_id.id)
                ], limit=1)
                
                if not warehouse:
                    raise ValidationError("No warehouse found for this company.")
                
                stock_location = warehouse.lot_stock_id

                if not stock_location:
                    raise ValidationError("Cannot determine stock location from warehouse.")

                # Only process if scrap was done
                if scrap_record.state == 'done':
                    # Get internal transfer picking type
                    picking_type = self.env['stock.picking.type'].search([
                        ('code', '=', 'internal'),
                        ('warehouse_id', '=', warehouse.id),
                    ], limit=1)
                    
                    if not picking_type:
                        # Fallback: get any internal picking type
                        picking_type = self.env['stock.picking.type'].search([
                            ('code', '=', 'internal'),
                            ('company_id', '=', scrap_record.company_id.id),
                        ], limit=1)
                    
                    if not picking_type:
                        raise ValidationError("No internal transfer picking type found.")

                    # 1. Create the picking (internal transfer)
                    picking_vals = {
                        'picking_type_id': picking_type.id,
                        'location_id': scrap_record.scrap_location_id.id,  # From scrap location
                        'location_dest_id': stock_location.id,             # To warehouse stock
                        'origin': f'Repair - {rec.name or rec.lot_id.name}',
                        'company_id': scrap_record.company_id.id,
                    }
                    picking = self.env['stock.picking'].create(picking_vals)

                    # 2. Create the stock move
                    move_vals = {
                        'name': f'Repair Return: {rec.lot_id.name}',
                        'product_id': scrap_record.product_id.id,
                        'product_uom_qty': scrap_record.scrap_qty,
                        'product_uom': scrap_record.product_uom_id.id,
                        'location_id': scrap_record.scrap_location_id.id,
                        'location_dest_id': stock_location.id,
                        'picking_id': picking.id,
                        'origin': f'Repair - {rec.name or rec.lot_id.name}',
                    }
                    move = self.env['stock.move'].create(move_vals)

                    # 3. Create the move line with lot and quantity BEFORE confirming
                    move_line = self.env['stock.move.line'].create({
                        'move_id': move.id,
                        'picking_id': picking.id,
                        'product_id': scrap_record.product_id.id,
                        'product_uom_id': scrap_record.product_uom_id.id,
                        'quantity': scrap_record.scrap_qty,
                        'lot_id': rec.lot_id.id,
                        'location_id': scrap_record.scrap_location_id.id,
                        'location_dest_id': stock_location.id,
                    })

                    # 4. Confirm the picking
                    picking.action_confirm()
                    picking.action_assign()

                    # 5. Ensure the move line has the lot assigned (in case it got reset)
                    if not move_line.lot_id:
                        move_line.lot_id = rec.lot_id.id
                    
                    # Set quantity done on move
                    move.quantity = scrap_record.scrap_qty

                    # 6. Validate the picking with immediate transfer context
                    picking.with_context(skip_backorder=True).button_validate()

                    # Store the scrap return picking reference
                    rec.scrap_return_picking_id = picking.id

            # 4. Reopen the installation record so box can be re-allocated
            if rec.donation_box_registration_installation_id:
                # raise UserError(_("Reopening the installation record is not allowed."))
                # Reset the installation status to allow re-allocation
                rec.donation_box_registration_installation_id.status = 'close'
            
            # 5. Delete the key record as a result it will be unlink from the bunch too
            self.env['key'].search([('lot_id', '=', self.lot_id.id)]).unlink()

            # 6. Update complain status to resolved
            rec.status = 'resolved'
        
        # Return notification for bulk operations
        if len(broken_records) > 1:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Repair Successful',
                    'message': f'{len(broken_records)} boxes have been repaired and are now available for re-allocation.',
                    'type': 'success',
                    'sticky': False,
                }
            }