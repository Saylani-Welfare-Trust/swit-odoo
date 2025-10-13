from odoo import fields, models, api, exceptions


key_status = [
    ('draft', 'Draft'),
    ('available', 'Available'),
    ('issued', 'Issued')
]


class Key(models.Model):
    _name = 'key'
    _description = 'Key'
    _inherit = ["mail.thread", "mail.activity.mixin"]


    rider_id = fields.Many2one('hr.employee', string="Rider ID", compute="_set_rider", store=True)
    donation_box_request_id = fields.Many2one('donation.box.requests', string="Donation Box Request ID")
    donation_box_registration_id = fields.Many2one('donation.box.registration', string="Donation Box Registration ID")
    key_location_id = fields.Many2one('key.location', string="Key Location ID", tracking=True)

    name = fields.Char('Key', tracking=True)
    box_no = fields.Char('Box No', tracking=True)
    lock_no = fields.Char('Lock No', tracking=True)
    full_key_location = fields.Char(related='key_location_id.name', string='Full Key Location', tracking=True)

    state = fields.Selection(selection=key_status, default='draft', string="Key Status")


    key_issuance_ids = fields.One2many('key.issuance', 'key_id', string="Key Issued IDs")


    @api.onchange('key_location_id')
    def _onchange_key_location_id(self):
        if self.key_location_id:
            if len(self.key_location_id.key_ids) > 50:
                raise exceptions.ValidationError(str(f'Key Bunch Limit Exceeded {len(self.key_location_id)}/50'))
            

    def action_available(self):
        self.state = 'available'