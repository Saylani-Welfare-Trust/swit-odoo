from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


status_selection = [
    ('draft', 'Draft'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
]


class DonationBoxRequest(models.Model):
    _name = 'donation.box.request'
    _description = "Donation Box Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]


    rider_id = fields.Many2one('hr.employee', string="Rider", tracking=True)
    picking_id = fields.Many2one('stock.picking', string="Picking", tracking=True)
    picking_type_id = fields.Many2one('stock.picking.type', string="Picking Type", default=lambda self: self.env.ref('bn_donation_box.donation_box_stock_picking_type', raise_if_not_found=False).id)
    source_location_id = fields.Many2one(related='picking_type_id.default_location_src_id', string="Source Location", store=True)
    destination_location_id = fields.Many2one(related='picking_type_id.default_location_dest_id', string="Destination Location", store=True)

    employee_category_id = fields.Many2one('hr.employee.category', string="Employee Category", default=lambda self: self.env.ref('bn_donation_box.installer_hr_employee_category', raise_if_not_found=False).id)
    
    name = fields.Char('Name', default="New")

    request_date = fields.Datetime(string='Request Date', default=fields.Datetime.now(), tracking=True)
    
    status = fields.Selection(selection=status_selection, string='Status', default='draft', tracking=True)

    key_tag_assign = fields.Boolean('Key Tag Assign', default=False)

    donation_box_request_line_ids = fields.One2many('donation.box.request.line', 'donation_box_request_id', string='Donation Request Line')
    donation_box_registration_installation_ids = fields.One2many('donation.box.registration.installation', 'donation_box_request_id', string='Donation Box Registration/Installation')



    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('donation_box_request') or ('New')

        return super(DonationBoxRequest, self).create(vals)
    
    def action_reject(self):
        self.status = 'rejected'

    def action_draft(self):
        self.env['donation.box.registration.installation'].search([('donation_box_request_id', '=', self.id)]).unlink()
        self.env['key'].search([('donation_box_request_id', '=', self.id)]).unlink()

        self.status = 'draft'
    
    def generate_records(self):
        for donation_box in self.donation_box_request_line_ids:
            if not self.key_tag_assign:
                RY = fields.Date.today().year
                BC = None

                if 'crystal' in donation_box.product_id.name.lower():
                    BC = '22'
                elif 'iron' in donation_box.product_id.name.lower():
                    BC = '23'
                else:
                    BC = '21'

                lock_no = donation_box.lock_no

                donation_box.key_tag = f'{str(RY)[2:]}{BC}{lock_no}-{donation_box.key_tag}'
                
            donation_box.lot_id.lot_consume = True

            donation_box_registration_obj = self.env['donation.box.registration.installation'].create({
                'donation_box_request_id': self.id,
                'lot_id': donation_box.lot_id.id,
                'lock_no': donation_box.lock_no,
                'product_id': donation_box.product_id.id,
                'installer_id': self.rider_id.id,
                'old_box_no': donation_box.old_box_no,
            })

            self.env['key'].create({
                'donation_box_request_id': self.id,
                'donation_box_registration_installation_id': donation_box_registration_obj.id,
                'lot_id': donation_box.lot_id.id,
                'lock_no': donation_box.lock_no,
                'name': donation_box.key_tag
            })

    def update_on_hand_quantity_with_stock_move(self, product, location, quantity):
        # Ensure the product and location exist
        if not product or not location:
            raise ValidationError("Product or Location not found.")
        
        # Create a stock move to adjust the quantity
        stock_move = self.env['stock.move'].create({
            'name': 'Stock Move for ' + product.name,
            'product_id': product.id,
            'product_uom_qty': quantity,
            'product_uom': product.uom_id.id,
            'location_id': location.id,
            'location_dest_id': location.id,  # Same location for adjustment
        })
        
        stock_move._action_confirm()
        stock_move._action_assign()
        stock_move._action_done()

    def check_lines(self):
        lot_ids = self.donation_box_request_line_ids.mapped('lot_id.id')
        duplicate_lots = [lot for lot in lot_ids if lot_ids.count(lot) > 1 and lot]

        if duplicate_lots:
            raise ValidationError('Duplicate Box No. found in request lines.')

    def action_approve(self):
        self.check_lines()

        self.generate_records()

        Picking = self.env['stock.picking']
        Move = self.env['stock.move']

        # create picking
        picking_vals = {
            'picking_type_id': self.picking_type_id.id,
            'location_id': self.source_location_id.id,
            'location_dest_id': self.destination_location_id.id,
            'origin': self.name,
        }
        picking = Picking.create(picking_vals)

        # create moves
        for line in self.donation_box_request_line_ids:
            move_vals = {
                'name': line.product_id.display_name,
                'product_id': line.product_id.id,
                'product_uom_qty': 1.0,
                'product_uom': line.product_id.uom_id.id,
                'location_id': self.source_location_id.id,
                'location_dest_id': self.destination_location_id.id,
                'picking_id': picking.id,
            }

            Move.create(move_vals)

        # confirm & assign
        picking.action_confirm()
        picking.action_assign()

        # add move lines with lot and qty_done
        mls = []
        for move in picking.move_ids_without_package:
            # match the request line for same product that has not been processed yet
            box_line = self.donation_box_request_line_ids.filtered(lambda l: l.product_id == move.product_id and not hasattr(l,'used'))
            if box_line:
                box = box_line[0]
                # mark as used in this loop so we don't reuse same line for duplicate products
                box.used = True
                mlvals = {
                    'move_id': move.id,
                    'picking_id': picking.id,
                    'product_id': move.product_id.id,
                    'product_uom_id': move.product_uom.id,
                    'qty_done': 1.0,
                    'lot_id': box.lot_id.id,
                    'location_id': move.source_location_id.id,
                    'location_dest_id': move.destination_location_id.id,
                }
                mls.append((0,0,mlvals))
        if mls:
            picking.write({'move_line_ids_without_package': mls})

        # final validation
        picking.button_validate()

        self.status = 'approved'
        self.picking_id = picking.id
        self.key_tag_assign = True