from odoo import models, fields, api
from odoo.exceptions import ValidationError


key_selection = [
    ('draft', 'Draft'),
    ('issued', 'Issued'),
    ('donation_receive', 'Donation Received'),
    ('returned', 'Returned'),
    ('overdue', 'Overdue')
]


class KeyIssuance(models.Model):
    _name = 'key.issuance'
    _description = 'Key Issuance'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = 'rider_name'


    key_id = fields.Many2one('key', string="Key", tracking=True)
    rider_id = fields.Many2one(related='key_id.rider_id', string="Rider", store=True)
    donation_box_registration_installation_id = fields.Many2one(related='key_id.donation_box_registration_installation_id', string="Donation Box Registartion / Installation", store=True)
    
    rider_name = fields.Char(related='rider_id.name', string="Rider", store=True)

    issued_on = fields.Datetime(string="Issued On", default=fields.Datetime.now)
    returned_on = fields.Datetime(string="Returned On")
    
    state = fields.Selection(selection=key_selection, default='draft', string="Status")

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


    def action_issue(self):
        for record in self:
            if self.search([('key_id', '=', record.key_id.id), ('state', '=', 'issued')]):
                raise ValidationError(str(f'Key ( {record.key_id.name} ) is already issued to {record.rider_id.name}'))

            record.state = 'issued'
            record.key_id.state = 'issued'

    def action_return(self):
        for record in self:
            if not record.donation_amount:
                raise ValidationError(str(f'Please enter the Amount of Donation Collected against key ( {self.key_id.name} )'))

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

        collection = self.env['rider.collection'].search([('lot_id', '=', data['lot_id']), ('state', '=', 'donation_submit'), ('date', '=', fields.Date.today())])
        
        if not collection:
            return {
                "status": "error",
                "body": f"Please first submit your Collection aganist {data['box_no']}",
            }
        elif collection and collection.amount != float(data['amount']):
            return {
                "status": "error",
                "body": f"Please enter the correct amount collected against {data['box_no']}",
            }

        collection.state = 'paid'

        key_obj = self.sudo().search([('key_id.lot_id', '=', data['lot_id']), ('state', '=', 'issued')])

        if not key_obj:
            return {
            "status": "error",
            "body": "Invalid Donation Box",
            }

        for key in key_obj:
            key.donation_amount = data['amount']
            key.action_donation_receive()

        return {
            "status": "success",
            "id": key_obj.id,
        }