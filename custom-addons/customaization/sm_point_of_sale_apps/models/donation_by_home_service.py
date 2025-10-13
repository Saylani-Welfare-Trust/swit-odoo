from odoo import api, fields, models, _, exceptions

donation_type_selection = [
    ('cash', 'Cash'),
    ('cheque',  'Cheque'),
    ('in_kind', 'In-Kind'),
]

class DonationByHomeServiceModel(models.Model):
    _name = 'donation.by.home.service'
    _description = 'Donation By Home Service Model'
    _rec_name = 'name'

    reference_number = fields.Char(string='Reference Number')
    street = fields.Char(string='Address')
    phone = fields.Char(string='Phone')
    name = fields.Char(string="name", required=True)
    donation_type = fields.Selection(selection=donation_type_selection, string='Donation Type')
    amount = fields.Integer(string='Amount')
    bank_name = fields.Char(string="Bank Name")
    cheque_number = fields.Char(string="Cheque Number")
    branch_id = fields.Many2one(comodel_name='res.company', string="Branch")
    delivery_charges_amount = fields.Integer(string='Delivery Charges')
    remark = fields.Char(string='Remark')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['reference_number'] = self.env['ir.sequence'].next_by_code('donation_by_home_service')
        result = super(DonationByHomeServiceModel, self).create(vals_list)
        return result

    @api.model
    def create_from_ui(self, partner):
        partner_id = self.create(partner).id
        return partner_id

