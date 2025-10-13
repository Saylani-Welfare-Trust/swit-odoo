from odoo import fields, models, api, _, exceptions


status_selection = [
    ('missing', 'Missing'),
    ('broken', 'Broken'),
    ('robbery', 'Robbery'),
]


class DonationBoxComplain(models.Model):
    _name = 'donation.box.complain'
    _description = 'Donation Box Complain'
    _inherit = ["mail.thread", "mail.activity.mixin"]


    rider_id = fields.Many2one('hr.employee', string="Rider ID", tracking=True)
    donation_box_id = fields.Many2one('donation.box.registration', string="Donation Box", tracking=True)
    
    box_no = fields.Char(related='donation_box_id.lot_id.name', string='Box No', store=True, tracking=True)
    name = fields.Char(related='donation_box_id.name', string='Requestor Name', store=True, tracking=True)
    contact_no = fields.Char(related='donation_box_id.contact_no', string='Contact No', store=True, tracking=True)
    location = fields.Char(related='donation_box_id.location', string='Requested Location', store=True, tracking=True)
    contact_person_name = fields.Char(related='donation_box_id.contact_person_name', string='Contact Person', store=True, tracking=True)

    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('process', 'Process'),
            ('resolved', 'Resolved'),
        ],
        string='Status',
        default='draft',
        tracking=True
    )

    box_status = fields.Selection(selection=status_selection, string="Box Status", tracking=True)

    installer_id = fields.Many2one(related='donation_box_id.installer_id', string="Installer ID")
    zone_id = fields.Many2one(related='donation_box_id.zone_id', string="Zone ID", store=True, tracking=True)
    city_id = fields.Many2one(related='donation_box_id.city_id', string="City ID", store=True, tracking=True)
    donor_id = fields.Many2one(related='donation_box_id.donor_id', string="Donor ID", store=True, tracking=True)
    sub_zone_id = fields.Many2one(related='donation_box_id.sub_zone_id', string="Sub Zone ID", store=True, tracking=True)
    donation_box_request_id = fields.Many2one(related='donation_box_id.donation_box_request_id', string="Donation Box Request ID", store=True)
    product_id = fields.Many2one(related='donation_box_id.product_id', string="Donation Box Category ID", store=True, tracking=True)
    installation_category_id = fields.Many2one(related='donation_box_id.installation_category_id', string="Installation Category ID", store=True, tracking=True)

    installation_date = fields.Date(related='donation_box_id.installation_date', string='Installation Date', store=True, tracking=True)

    remarks = fields.Text('Remarks', tracking=True)


    def action_process(self):
        self.write({
            'state': 'process',
        })
    
    def action_resolve(self):
        self.write({
            'state': 'resolved',
        })