from odoo import models, fields, api
from odoo.exceptions import ValidationError


box_status_selection = [
    ('not_installed', 'Not Installed'),
    ('installed', 'Installed'),
]

status_selection = [
    ('draft', 'Draft'),
    ('installed', 'Installed'),
    ('approved', 'Approved'),
    ('available', 'Available')
]


class DonationBoxRegistrationInstallation(models.Model):
    _name = 'donation.box.registration.installation'
    _description = 'Donation Box Registration'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = 'shop_name'


    donation_box_request_id = fields.Many2one('donation.box.request', string="Donation Box Request")
    lot_id = fields.Many2one('stock.lot', string="Lot")
    donor_id = fields.Many2one('res.partner', string="Donor", tracking=True)
    installation_category_id = fields.Many2one('installation.category', string="Installation Category", tracking=True)
    product_id = fields.Many2one('product.product', string="Box Category")
    country_id = fields.Many2one('res.country', string="Phone Code")
    
    rider_id = fields.Many2one('hr.employee', string="Rider", tracking=True)
    installer_id = fields.Many2one('hr.employee', string="Installer", tracking=True)
    employee_category_1_id = fields.Many2one('hr.employee.category', string="Employee 1 Category", default=lambda self: self.env.ref('bn_donation_box.donation_box_rider_hr_employee_category', raise_if_not_found=False).id)
    employee_category_2_id = fields.Many2one('hr.employee.category', string="Employee 2 Category", default=lambda self: self.env.ref('bn_donation_box.installer_hr_employee_category', raise_if_not_found=False).id)
    
    city_id = fields.Many2one('account.analytic.account', string="City", tracking=True)
    zone_id = fields.Many2one('account.analytic.account', string="Zone", tracking=True)
    sub_zone_id = fields.Many2one('sub.zone', string="Sub Zone", tracking=True)

    name = fields.Char(related='donation_box_request_id.name', string="Name", store=True)
    shop_name = fields.Char('Shop Name', tracking=True)
    contact_no = fields.Char('Contact No', size=10, tracking=True)
    location = fields.Char('Requested Location', tracking=True)
    contact_person = fields.Char('Contact Person', tracking=True)
    old_box_no = fields.Char('Old Box No.')

    installation_date = fields.Date('Installation Date', default=fields.Date.today(), tracking=True)

    complain_center_ids = fields.One2many('donation.box.complain.center', 'donation_box_registration_installation_id', string="Complain Centers")

    status = fields.Selection(selection=status_selection, string='Status', default='draft', tracking=True)
    box_status = fields.Selection(selection=box_status_selection, string="Box Status", default='not_installed', tracking=True)

    
    def action_install(self):
        self.box_state = 'installed'
        self.state = 'installed'

    def action_approved(self):
        key = self.env['key'].search([('lot_id', '=', self.lot_id.id)])

        if key:
            key.key_bunch_id = self.key_bunch_id.id
            key.rider_id = self.rider_id.id

            key.action_available()

        self.status = 'available'

    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('donation_box') or ('New')

        return super(DonationBoxRegistrationInstallation, self).create(vals)

    # def action_create_donor(self):
    #     return {
    #         'name': 'Donor Registation',
    #         'view_mode': 'form',
    #         'view_id': self.env.ref('bn_profile_management.custom_donor_res_partner_view_form').id,
    #         'res_model': 'res.partner',
    #         'type': 'ir.actions.act_window',
    #         'context': {
    #             'default_is_donee': False,
    #             'default_donor_type': 'individual',
    #             'default_registration_category': 'donor',
    #         },
    #         'target': 'new',
    #     }