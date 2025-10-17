from odoo import models, fields, api
from odoo.exceptions import ValidationError


key_status = [
    ('draft', 'Draft'),
    ('available', 'Available'),
    ('issued', 'Issued')
]


class Key(models.Model):
    _name = 'key'
    _description = 'Key'
    _inherit = ["mail.thread", "mail.activity.mixin"]


    donation_box_request_id = fields.Many2one('donation.box.request', string="Donation Box Request")
    donation_box_registration_installation_id = fields.Many2one('donation.box.registration.installation', string="Donation Box Registration")
    key_bunch_id = fields.Many2one(related='donation_box_registration_installation_id.key_bunch_id', string="Key Bunch", store=True)
    rider_id = fields.Many2one(related='key_bunch_id.rider_id', string="Rider", store=True)

    name = fields.Char('Key')
    lot_id = fields.Many2one('stock.lot', string="Lot")
    lock_no = fields.Char('Lock No')

    state = fields.Selection(selection=key_status, default='draft', string="Status")

    key_issuance_ids = fields.One2many('key.issuance', 'key_id', string="Key Issued")


    @api.onchange('key_bunch_id')
    def _onchange_key_bunch_id(self):
        if self.key_bunch_id:
            if len(self.key_bunch_id.key_ids) > 50:
                raise ValidationError(str(f'Key Bunch Limit Exceeded {len(self.key_bunch_id)}/50'))
            

    def action_available(self):
        self.state = 'available'