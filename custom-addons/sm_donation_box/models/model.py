from odoo import models, fields, api, exceptions, _
from datetime import datetime
import random
import string


class DonationBoxesRequestsModel(models.Model):
    _name = 'donation.box.requests'
    _description = 'Donation Boxes Requests Models'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = 'request_type'


    def _get_current_datetime(self):
        current_date = datetime.now()
        return current_date
    
    request_type = fields.Selection(
        [
            ('internal', 'Internal'),
            ('external', 'External'),
        ],
        string='Request Type',
        default='internal'
    )
    request_date = fields.Datetime(
        string='Request Date',
        default=_get_current_datetime,
    )
    status = fields.Selection(
        [
            ('draft', 'Draft'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        string='Status',
        default='draft',
        tracking=True
    )
    rider_id = fields.Many2one('hr.employee', string="Rider ID", tracking=True)


    # Syed Owais Noor
    rider_name = fields.Char(related='rider_id.name', string="Rider Name", tracking=True, store=True)
    name = fields.Char('Name')

    old_system_record = fields.Text('Old System Record')

    donation_box_request_line_ids = fields.One2many('donation.box.request.line', 'donation_box_request_id', string='Product IDs')
    donation_box_registration_ids = fields.One2many('donation.box.registration', 'donation_box_request_id', string='Donation Box Registration IDs')



    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('donation_box_registration') or ('New')
        return super().create(vals)
    
    def generate_records(self):
        # raise exceptions.UserError('Funcationality Coming Soon...')

        for donation_box in self.donation_box_request_line_ids:
            if donation_box.box_no:
                donation_box.box_no = ""
            if donation_box.keys_tag:
                donation_box.keys_tag = ""

            for loop, lock_no in zip(range(donation_box.quantity), donation_box.lock_no.split(',')):
                RY = fields.Date.today().year
                BC = None

                if donation_box.product_id.name == 'Donation Box ( Large Crystal )':
                    BC = '22'
                elif donation_box.product_id.name == 'Donation Box ( Large Iron )':
                    BC = '23'
                elif donation_box.product_id.name == 'Donation Box ( Small Box )':
                    BC = '21'
                    
                BRN = ''.join(random.choices(string.digits, k=4))
                KRN = ''.join(random.choices(string.digits, k=2))

                if donation_box.box_no:
                    donation_box.box_no += f', CB-{str(RY)[2:]}{BC}{BRN}'
                else:
                    donation_box.box_no = f'CB-{str(RY)[2:]}{BC}{BRN}'
                
                if donation_box.keys_tag:
                    donation_box.keys_tag += f', {str(RY)[2:]}{BC}{BRN}-{KRN}'
                else:
                    donation_box.keys_tag = f'{str(RY)[2:]}{BC}{BRN}-{KRN}'

                donation_box_registration_obj = self.env['donation.box.registration'].create({
                    'donation_box_request_id': self.id,
                    'box_no': f'{RY}-{BC}{BRN}',
                    'product_id': donation_box.product_id.id,
                    'installer_id': self.rider_id.id,
                    'analytic_plan_id': donation_box.analytic_plan_id.id
                })

                self.env['key'].create({
                    'donation_box_request_id': self.id,
                    'donation_box_registration_id': donation_box_registration_obj.id,
                    'box_no': f'{RY}-{BC}{BRN}',
                    'lock_no': lock_no,
                    'name': f'{RY}{BC}{BRN}-{KRN}'
                })

    # End

    def action_button_draft(self):
        small_box = large_iron_box = large_crystal_box = 0

        for donation_box in self.donation_box_request_line_ids:
            if donation_box.product_id.name == 'Donation Box ( Large Crystal )':
                large_crystal_box += donation_box.quantity
            elif donation_box.product_id.name == 'Donation Box ( Large Iron )':
                large_iron_box += donation_box.quantity
            elif donation_box.product_id.name == 'Donation Box ( Small Box )':
                small_box += donation_box.quantity

        self.rider_id.small_box_count -= small_box
        self.rider_id.large_iron_box_count -= large_iron_box
        self.rider_id.large_crystal_box_count -= large_crystal_box

        self.env['donation.box.registration'].search([('donation_box_request_id', '=', self.id)]).unlink()
        self.env['key'].search([('donation_box_request_id', '=', self.id)]).unlink()

        self.write({
            'status': 'draft',
        })

    def update_on_hand_quantity_with_stock_move(self, product, location, quantity):
        # Ensure the product and location exist
        if not product or not location:
            raise exceptions.ValidationError("Product or Location not found.")
        
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

    def action_button_approved(self):
        small_box = large_iron_box = large_crystal_box = 0

        for donation_box in self.donation_box_request_line_ids:
            if donation_box.product_id.name == 'Donation Box ( Large Crystal )':
                large_crystal_box += donation_box.quantity
            elif donation_box.product_id.name == 'Donation Box ( Large Iron )':
                large_iron_box += donation_box.quantity
            elif donation_box.product_id.name == 'Donation Box ( Small Box )':
                small_box += donation_box.quantity

        self.rider_id.small_box_count += small_box
        self.rider_id.large_iron_box_count += large_iron_box
        self.rider_id.large_crystal_box_count += large_crystal_box

        self.generate_records()

        # for donation_box in self.donation_box_request_line_ids:
        #     self.update_on_hand_quantity_with_stock_move(donation_box.product_id, donation_box.warehouse_loc_id, donation_box.quantity)

        self.write({
            'status': 'approved',
        })

    def action_button_rejected(self):
        self.write({
            'status': 'rejected',
        })


class DonationBoxRequestLine(models.Model):
    _name = 'donation.box.request.line'
    _description = 'Donation Box Request Line'


    donation_box_request_id = fields.Many2one('donation.box.requests', string="Donation Box Request ID")
    product_id = fields.Many2one('product.product', string="Product ID")
    warehouse_loc_id = fields.Many2one('stock.location', string="Warehouse/Location ID")
    analytic_plan_id = fields.Many2one('account.analytic.plan', string="Analytic Plan ID")

    quantity = fields.Integer('Box Quantity', default=1)

    box_no = fields.Char('Box No.', tracking=True)
    lock_no = fields.Char('Lock No.', tracking=True)
    keys_tag = fields.Char('Keys Tag', tracking=True)
    no_of_keys = fields.Char('No. of Keys', compute="_calculate_keys", store=True, tracking=True)


    @api.depends('quantity')
    def _calculate_keys(self):
        for rec in self:
            rec.no_of_keys = 3 * rec.quantity


class Product(models.Model):
    _inherit = 'product.product'
    
    
    is_donation_box = fields.Boolean('Is Donation Box', tracking=True)


class HREmployee(models.Model):
    _inherit = 'hr.employee'
    
    
    small_box_count = fields.Integer('Small Box Count', tracking=True)
    large_iron_box_count = fields.Integer('Large Iron Box Count', tracking=True)
    large_crystal_box_count = fields.Integer('Large Crystal Box Count', tracking=True)