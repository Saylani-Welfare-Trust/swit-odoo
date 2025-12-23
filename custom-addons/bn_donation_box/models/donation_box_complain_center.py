from odoo import fields, models, api
from odoo.exceptions import ValidationError


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
    return_picking_id = fields.Many2one('stock.picking', string="Return", tracking=True)
    scrap_picking_id = fields.Many2one('stock.scrap', string="Scrap", tracking=True)

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
        self.status = 'process'
    
    def action_resolve(self):
        if self.box_status != 'return':
            self.donation_box_registration_installation_id.status = 'close'
            self.lot_id.is_not_return = True

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
        """Perform a serial-based stock return for the donation box."""
        for rec in self:

            if not rec.lot_id:
                raise ValidationError("Please select a Serial (Lot) to return.")

            registration = rec.donation_box_registration_installation_id
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

            # 2. Create return wizard
            return_wizard = self.env['stock.return.picking'].create({
                'picking_id': picking.id,
            })

            # 3. Keep only the selected serial
            serial_used = picking.move_line_ids.filtered(lambda ml: ml.lot_id.id == rec.lot_id.id)
            if not serial_used:
                raise ValidationError("This serial does not belong to the selected picking.")

            # Update return lines
            for line in return_wizard.product_return_moves:
                if line.product_id == serial_used.product_id:
                    line.quantity = 1
                else:
                    line.quantity = 0

            # 4. Create the return picking
            res = return_wizard.create_returns()   # res = {'res_id': return picking ID}
            return_picking = self.env['stock.picking'].browse(res['res_id'])

            # 5. Assign the same serial number to return move line
            return_move_line = return_picking.move_line_ids.filtered(
                lambda ml: ml.product_id == serial_used.product_id
            )

            if not return_move_line:
                # create move line if missing
                return_move_line = self.env['stock.move.line'].create({
                    'move_id': return_picking.move_ids_without_package.filtered(
                        lambda m: m.product_id == serial_used.product_id
                    ).id,
                    'picking_id': return_picking.id,
                    'product_id': serial_used.product_id.id,
                    'product_uom_id': serial_used.product_uom_id.id,
                    'quantity': 1,
                    'lot_id': rec.lot_id.id,
                    'location_id': picking.location_dest_id.id,
                    'location_dest_id': picking.location_id.id,
                })
            else:
                # update existing move line
                return_move_line.lot_id = rec.lot_id.id
                return_move_line.quantity = 1

            # 6. Validate the return picking
            return_picking.button_validate()

            # 7. Close installation
            registration.status = 'close'

            # 8. Close complain
            rec.status = 'resolved'
            rec.return_picking_id = return_picking.id
            
            # 9. Lot consume
            rec.lot_id.lot_consume = False

    def action_scrap(self):
        """Scrap the selected serial (lot) instead of returning picking."""
        for rec in self:

            if not rec.lot_id:
                raise ValidationError("Please select a Serial (Lot) to scrap.")

            registration = rec.donation_box_registration_installation_id
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

    def action_repair(self):
        """
        Repair broken donation boxes (single or bulk).
        Once repaired, the box becomes available in stock for re-allocation and installation.
        """
        broken_records = self.filtered(lambda r: r.box_status == 'broken')
        
        if not broken_records:
            raise ValidationError("No broken boxes selected for repair. Only boxes with 'Broken' status can be repaired.")

        for rec in broken_records:
            # 1. Change box status to 'repaired'
            rec.box_status = 'repaired'
            
            # 2. Make the lot available again for re-allocation
            if rec.lot_id:
                # Reset lot flags so it becomes available in stock
                rec.lot_id.lot_consume = False
                rec.lot_id.is_not_return = False
            
            # 3. If there's a scrap record, we need to reverse the scrap
            # by creating a stock move from scrap location back to stock
            if rec.scrap_picking_id:
                scrap = rec.scrap_picking_id

                # Get the original stock location for this product (usually warehouse stock)
                stock_location = scrap.location_id

                if stock_location:
                    # Original scrap move
                    scrap_move = scrap
                    if scrap_move.state == 'done':
                        # Create a reverse move from scrap location → stock location
                        reverse_move_vals = {
                            'name': f'Repair Return: {rec.lot_id.name}',
                            'product_id': scrap_move.product_id.id,
                            'product_uom_qty': scrap_move.scrap_qty,
                            'product_uom': scrap_move.product_uom_id.id,
                            'location_id': scrap_move.scrap_location_id.id,   # Scrap location
                            'location_dest_id': scrap.location_id.id,          # Internal stock
                            'lot_ids': [(4, rec.lot_id.id)],
                            'origin': f'Repair - {rec.name or rec.lot_id.name}',
                        }

                        reverse_move = self.env['stock.move'].create(reverse_move_vals)
                        reverse_move._action_confirm()
                        reverse_move._action_assign()
                        reverse_move._action_done()
                else: raise ValidationError("Cannot determine stock location to reverse scrap operation.")

            # 4. Reopen the installation record so box can be re-allocated
            if rec.donation_box_registration_installation_id:
                # Reset the installation status to allow re-allocation
                rec.donation_box_registration_installation_id.status = 'available'
            
            # 5. Update complain status to resolved
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