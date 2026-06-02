from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

import logging

_logger = logging.getLogger(__name__)

key_selection = [
    ('draft', 'Draft'),
    ('issued', 'Issued'),
    ('donation_receive', 'Donation Received'),
    ('overdue', 'Overdue'),
    ('pending', 'Pending'),
    ('returned', 'Returned'),
]

action_type_selection = [
    ('bulk', 'Bulk'),
    ('manual', 'Manual'),
]


class KeyIssuance(models.Model):
    _name = 'key.issuance'
    _description = 'Key Issuance'
    _inherit = ["mail.thread", "mail.activity.mixin"]


    rider_id = fields.Many2one('hr.employee', string="Rider", tracking=True)
    key_id = fields.Many2one('key', string="Key", tracking=True)
    donation_box_registration_installation_id = fields.Many2one(related='key_id.donation_box_registration_installation_id', string="Donation Box Registartion / Installation", store=True)
    
    name = fields.Char('Key Name', default="New")
    key_name = fields.Char(related='key_id.name', string="Key Name", store=True)

    issued_on = fields.Datetime('Issued On', default=fields.Datetime.now)
    issue_date = fields.Date('Issued Date', default=fields.Date.today)
    returned_on = fields.Datetime('Returned On')
    
    state = fields.Selection(selection=key_selection, default='draft', string="Status")
    action_type = fields.Selection(selection=action_type_selection, default='bulk', string="Action Type")

    donation_amount = fields.Float('Donation Amount')

    shop_name = fields.Char(related='donation_box_registration_installation_id.shop_name', string='Requestor Name', store=True)
    contact_no = fields.Char(related='donation_box_registration_installation_id.contact_no', string='Contact No', store=True)
    location = fields.Char(related='donation_box_registration_installation_id.location', string='Requested Location', store=True)
    contact_person = fields.Char(related='donation_box_registration_installation_id.contact_person', string='Contact Person', store=True)

    installer_id = fields.Many2one(related='donation_box_registration_installation_id.installer_id', string="Installer")
    donor_id = fields.Many2one(related='donation_box_registration_installation_id.donor_id', string="Donor", store=True)
    lot_id = fields.Many2one(related='donation_box_registration_installation_id.lot_id', string="Donor", store=True)
    city_id = fields.Many2one(related='donation_box_registration_installation_id.city_id', string="City", store=True)
    zone_id = fields.Many2one(related='donation_box_registration_installation_id.zone_id', string="Zone", store=True)
    sub_zone_id = fields.Many2one(related='donation_box_registration_installation_id.sub_zone_id', string="Sub Zone", store=True)
    key_bunch_id = fields.Many2one(related='donation_box_registration_installation_id.key_bunch_id', string="Key Bunch", store=True)
    donation_box_request_id = fields.Many2one(related='donation_box_registration_installation_id.donation_box_request_id', string="Donation Box Request", store=True)
    product_id = fields.Many2one(related='donation_box_registration_installation_id.product_id', string="Donation Box Category", store=True)
    installation_category_id = fields.Many2one(related='donation_box_registration_installation_id.installation_category_id', string="Installation Category", store=True)

    installation_date = fields.Date(related='donation_box_registration_installation_id.installation_date', string='Installation Date', store=True)
    is_fcb = fields.Boolean('Is FCB Collection', default=False)
    is_cfb = fields.Boolean('Is CFB Collection', default=False)

    def action_issue(self):
        for record in self:
            if self.search([('key_id', '=', record.key_id.id), ('state', '=', 'issued')]):
                raise ValidationError(str(f'Key ( {record.key_id.name} ) is already issued to {record.rider_id.name}'))

            record.donation_box_registration_installation_id.key_issuance = True

            record.state = 'issued'
            record.key_id.state = 'issued'

            # CREATE rider.collection record
            self.env['rider.collection'].create({
                'rider_id': record.rider_id.id,
                'donation_box_registration_installation_id': record.key_id.donation_box_registration_installation_id.id,
                'lot_id': record.key_id.lot_id.id,
                'date': record.issue_date,
            })

    def action_return(self):
        for record in self:
            record.state = 'returned'
            record.returned_on = fields.Datetime.now()
            record.key_id.state = 'available'

    def action_donation_receive(self):
        for rec in self:
            rec.state = 'donation_receive'

    def action_overdue(self):
        for record in self:
            record.state = 'overdue'
    def action_create_pos_record(self):
        """Create a donation box (FCB) from selected foreign currency lines."""
        _logger.info(f"Starting FCB creation for lines: {self.ids}")
        
        # Validate selected lines
        invalid_lines = self.filtered(lambda rec: rec.state != 'converted')
        if invalid_lines:
            raise UserError('Only converted foreign currency lines can be used. Please select only converted lines.')

        selected_amount = sum(self.mapped('exchanged_amount'))
        if not selected_amount:
            raise UserError('Please select converted foreign currency lines with a non-zero exchanged amount.')

        if any(not rec.lot_id for rec in self):
            raise UserError('Selected foreign currency lines must have a box assigned.')
        
        lot_ids = self.mapped('lot_id')
        if len(lot_ids) != 1:
            raise UserError('Selected foreign currency lines must belong to the same box.')

        lot = lot_ids[0]

        # Find or create "Foreign Currency" rider
        fc_rider = self.env['hr.employee'].search([('name', '=', 'Foreign Currency')], limit=1)
        if not fc_rider:
            fc_rider = self.env['hr.employee'].create({
                'name': 'Foreign Currency',
            })

        # Find the donation box registration for this lot
        box = self.env['donation.box.registration.installation'].search([('lot_id', '=', lot.id)], limit=1)
        if not box:
            raise UserError('Could not find a donation box registration for the selected box.')

        # Create rider collection with FCB remarks
        rider_collection = self.env['rider.collection'].create({
            'rider_id': fc_rider.id,
            'date': fields.Date.today(),
            'donation_box_registration_installation_id': box.id,
            'state': 'donation_submit',
            'amount': selected_amount,
            'remarks': 'FCB',
        })
        
        _logger.info(f"Created rider collection: {rider_collection.id} with remarks 'FCB'")

        # Link the foreign currency lines to this collection
        self.write({'rider_collection_id': rider_collection.id})
        _logger.info(f"Linked foreign currency lines {self.ids} to collection {rider_collection.id}")

        # Create key issuance for this box
        key = self.env['key'].search([
            ('donation_box_registration_installation_id', '=', box.id),
            ('state', 'in', ['available', 'issued'])
        ], limit=1)
        
        if not key:
            key = self.env['key'].search([
                ('donation_box_registration_installation_id', '=', box.id)
            ], limit=1)

        if key:
            key_issuance_vals = {
                'rider_id': fc_rider.id,
                'key_id': key.id,
                'issue_date': fields.Date.today(),
                'issued_on': fields.Datetime.now(),
                'state': 'donation_receive',
                'action_type': 'manual',
                'donation_amount': selected_amount,
            }
            
            if 'rider_collection_id' in self.env['key.issuance']._fields:
                key_issuance_vals['rider_collection_id'] = rider_collection.id
            
            key_issuance = self.env['key.issuance'].create(key_issuance_vals)
            _logger.info(f"Created key issuance: {key_issuance.id}")

        # CHANGE STATE TO PAYMENT_RECEIVED
        self.write({'state': 'payment_received'})
        _logger.info(f"Updated foreign currency lines {self.ids} to state 'payment_received'")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'FCB Created',
                'message': f'FCB collection created with amount {selected_amount}. Please collect payment from POS.',
                'type': 'success',
                'sticky': False,
            }
        }
    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('key_issuance') or ('New')

        return super(KeyIssuance, self).create(vals)