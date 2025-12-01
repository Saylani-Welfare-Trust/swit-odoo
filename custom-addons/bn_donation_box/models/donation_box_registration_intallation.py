from odoo import models, fields, api, _
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

    name = fields.Char('Name', default="New")
    request_no = fields.Char(related='donation_box_request_id.name', string="Request No.", store=True)
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
        if not self.donor_id:
            donor = self.env['res.partner'].create({
                'name': self.shop_name,
                'street': self.location,
                'country_code_id': self.country_id.id,
                'mobile': self.contact_no,
                'category_id': [(6, 0, [2, 4, 14])],
            })

            self.donor_id = donor.id

        self.box_status = 'installed'
        self.status = 'installed'

    def action_approved(self):
        if not self.donor_id:
            donor = self.env['res.partner'].create({
                'name': self.shop_name,
                'street': self.location,
                'country_code_id': self.country_id.id,
                'mobile': self.contact_no,
                'category_id': [(6, 0, [2, 4, 14])],
            })

            self.donor_id = donor.id

        key = self.env['key'].search([('lot_id', '=', self.lot_id.id)])

        if key:
            key.key_bunch_id = self.key_bunch_id.id
            key.rider_id = self.rider_id.id
            key.donation_box_request_id = self.donation_box_request_id.id
            key.donation_box_registration_installation_id = self.id

            key.action_available()

        self.status = 'available'

    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('donation_box') or ('New')

        return super(DonationBoxRegistrationInstallation, self).create(vals)
    
    def install_donation_box(self, records):
        # raise ValidationError(str(records))
        
        for rec in records:
            rec.action_install()
    
    def add_demo_rider(self, records):
        for rec in records:
            rec.rider_id = 1 # Default Odoo Administrator ID

    def approve_donation_box(self, records):
        for rec in records:
            rec.action_approved()