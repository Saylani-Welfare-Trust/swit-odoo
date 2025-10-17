from odoo import fields, models


box_status_selection = [
    ('missing', 'Missing'),
    ('broken', 'Broken'),
    ('robbery', 'Robbery'),
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


    rider_id = fields.Many2one('hr.employee', string="Rider", tracking=True)
    donation_box_registration_installation_id = fields.Many2one('donation.box.registration.installation', string="Donation Box", tracking=True)

    employee_category_id = fields.Many2one('hr.employee.category', string="Employee Category", default=lambda self: self.env.ref('bn_donation_box.donation_box_rider_hr_employee_category', raise_if_not_found=False).id)
    
    lot_id = fields.Many2one(related='donation_box_registration_installation_id.lot_id', string='Box No', store=True, tracking=True)
    
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
        self.status = 'resolved'