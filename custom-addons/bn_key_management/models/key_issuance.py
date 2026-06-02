from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
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

    @api.model
    def set_donation_amount(self, data):
        if not data:
            return {
                "status": "error",
                "body": "Please specify Key and Collection Amount",
            }

        collection_id = data.get('collection_id')
        if not collection_id:
            return {
                "status": "error",
                "body": "Collection ID is required",
            }
        
        collection = self.env['rider.collection'].browse(collection_id)
        
        if not collection.exists():
            return {
                "status": "error",
                "body": f"Collection record not found for {data.get('box_no', 'unknown box')}",
            }
        
        # ========== HANDLE CFB COLLECTIONS (Counterfeit) ==========
        if collection.remarks == 'CFB':
            collection.write({'state': 'paid'})
            
            if collection.counterfeit_note_ids:
                collection.counterfeit_note_ids.write({'state': 'paid'})
                _logger.info(f"Updated {len(collection.counterfeit_note_ids)} CFB notes to 'paid'")
            
            counterfeit_donor = self.env['res.partner'].search([
                ('name', 'ilike', 'Counterfeit')
            ], limit=1)
            
            if not counterfeit_donor:
                counterfeit_donor = self.env['res.partner'].create({
                    'name': 'Counterfeit Donor',
                    'is_company': False,
                    'customer_rank': 1,
                })
            
            return {
                "status": "success",
                "donor_id": counterfeit_donor.id,
                "is_cfb": True,
            }
        
        # ========== HANDLE FCB COLLECTIONS (Foreign Currency) ==========
        if collection.remarks == 'FCB':
            # Mark collection as paid
            collection.write({'state': 'paid'})
            
            # Find foreign currency lines linked to this collection using the rider_collection_id field
            foreign_currency_lines = self.env['foreign.currency'].search([
                ('rider_collection_id', '=', collection.id)
            ])
            
            # Update foreign currency lines from PAYMENT_RECEIVED to PAID state
            if foreign_currency_lines:
                # Only update lines that are in 'payment_received' state
                lines_to_update = foreign_currency_lines.filtered(
                    lambda line: line.state == 'payment_received'
                )
                if lines_to_update:
                    lines_to_update.write({'state': 'paid'})
                    _logger.info(f"Updated {len(lines_to_update)} FCB lines from 'payment_received' to 'paid' state")
                else:
                    _logger.warning(f"No FCB lines in 'payment_received' state found for collection {collection.id}")
            else:
                _logger.warning(f"No foreign currency lines found for collection {collection.id}")
            
            # Find or create FCB Donor
            fcb_donor = self.env['res.partner'].search([
                ('name', 'ilike', 'Foreign Currency Donor')
            ], limit=1)
            
            if not fcb_donor:
                fcb_donor = self.env['res.partner'].create({
                    'name': 'Foreign Currency Donor',
                    'is_company': False,
                    'customer_rank': 1,
                })
            
            return {
                "status": "success",
                "donor_id": fcb_donor.id,
                "is_fcb": True,
            }
        
        # ========== NORMAL COLLECTIONS ==========
        if collection.state != 'donation_submit':
            return {
                "status": "error",
                "body": f"Please first submit your Collection against {data['box_no']}",
            }
        
        if collection.amount != float(data['amount']):
            return {
                "status": "error",
                "body": f"Please enter the correct amount collected against {data['box_no']}",
            }

        key_obj = self.sudo().search([('rider_collection_id', '=', collection_id)], limit=1)
        if not key_obj:
            key_obj = self.sudo().search([
                ('key_id.lot_id', '=', data['lot_id']),
                ('issue_date', '=', data['date']),
                ('state', 'in', ['issued', 'overdue'])
            ], limit=1)

        if not key_obj:
            return {
                "status": "error",
                "body": "Invalid Donation Box",
            }

        box = self.env['donation.box.registration.installation'].search([
            ('lot_id', '=', data['lot_id']),
            ('shop_name', '=', data['shop_name']),
            ('contact_person', '=', data['contact_person']),
            ('contact_no', '=', data['contact_number']),
            ('location', '=', data['box_location']),
        ], limit=1)

        if not data['check_validation']:
            key_obj.donation_amount = data['amount']
            key_obj.action_donation_receive()
            collection.state = 'paid'

            return {
                "status": "success"
            }

        return {
            "status": "success",
            "id": key_obj.id,
            "donor_id": box.donor_id.id
        }
    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('key_issuance') or ('New')

        return super(KeyIssuance, self).create(vals)