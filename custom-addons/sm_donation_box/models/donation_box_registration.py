from odoo import fields, models, api, _, exceptions

import re


# Regular expression for mobile number (with optional country code)
# mobile_pattern = r'^\+?[1-9]\d{1,14}$|^\+?[1-9]\d{1,14}(\s?\d+)+$|^\d{11}$'
mobile_pattern = r"^(?:\+92|92|0)[\s-]?[3-9][0-9]{2}[\s-]?[0-9]{7}$"

box_state_selection = [
    ('not_installed', 'Not Installed'),
    ('installed', 'Installed'),
]


class DonationBoxRegistration(models.Model):
    _name = 'donation.box.registration'
    _description = 'Donation Box Registration'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = 'name'

    box_no = fields.Char('Box No', tracking=True)
    name = fields.Char('Shop Name', tracking=True)
    contact_no = fields.Char('Contact No', tracking=True)
    location = fields.Char(string='Requested Location', tracking=True)
    contact_person_name = fields.Char('Contact Person', tracking=True)

    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('installed', 'Installed'),
            ('approved', 'Approved'),
            ('available', 'Available'),
        ],
        string='Status',
        default='draft',
        tracking=True
    )
    box_state = fields.Selection(selection=box_state_selection, string="Box Status", default='not_installed', tracking=True)

    city_id = fields.Many2one('res.company', string="City ID", tracking=True)
    zone_id = fields.Many2one('res.company', string="Zone ID", default=lambda self: self.env.company.id, tracking=True)
    sub_zone_id = fields.Many2one('sub.zone', string="Sub Zone ID", tracking=True)
    donor_id = fields.Many2one('res.partner', string="Donor ID", tracking=True)
    donation_box_request_id = fields.Many2one('donation.box.requests', string="Donation Box Request ID")
    product_id = fields.Many2one('product.product', string="Donation Box Category ID", tracking=True)
    installation_category_id = fields.Many2one('installation.category', string="Installation Category ID", tracking=True)
    installer_id = fields.Many2one('hr.employee', string="Installer ID")
    rider_id = fields.Many2one('hr.employee', string="Rider ID")
    analytic_plan_id = fields.Many2one('account.analytic.plan', string="Analytic Plan ID")
    lot_id = fields.Many2one('stock.lot', string="Lot ID")

    installation_date = fields.Date('Installation Date', default=fields.Date.today(), tracking=True)

    complain_ids = fields.One2many('donation.box.complain', 'donation_box_id', string="Complain IDs")



    @api.model
    def create(self, vals):
        # raise exceptions.UserError(str(vals)+ " <-> " +str(re.match(mobile_pattern, vals.get('contact_no'))))

        if vals.get('contact_no') and not re.match(mobile_pattern, vals.get('contact_no')):
            raise exceptions.ValidationError(str(f'Invalid Contact No. {vals.get("contact_no")}'))
        
        return super(DonationBoxRegistration, self).create(vals)

    # End

    def action_installed(self):
        self.box_state = 'installed'
        self.state = 'installed'

    def action_button_approved(self):
        key = self.env['key'].search([('box_no', '=', self.lot_id.name)])

        if key:
            key.key_location_id = self.key_location_id.id
            key.rider_id = self.rider_id.id

            key.action_available()

        self.write({
            'state': 'available',
        })

    def action_create_donor(self):
        return {
            'name': 'Donor Registation',
            'view_mode': 'form',
            'view_id': self.env.ref('bn_profile_management.custom_donor_res_partner_view_form').id,
            'res_model': 'res.partner',
            'type': 'ir.actions.act_window',
            'context': {
                'default_is_donee': False,
                'default_donor_type': 'individual',
                'default_registration_category': 'donor',
            },
            'target': 'new',
        }


class ResPartner(models.Model):
    _inherit = 'res.partner'


    donation_box_registration_ids = fields.One2many('donation.box.registration', 'donor_id', string="Donation Box Registration IDs")