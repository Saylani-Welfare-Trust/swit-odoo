from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


state_selection = [
    ('available', 'Available'),
    ('full', 'Full')
]


class QurbaniCowSlaughter(models.Model):
    _name = 'qurbani.cow.slaughter'
    _description = "Qurbani Cow Slaughter"


    hijri_id = fields.Many2one('hijri', string="Hijri")
    day_id = fields.Many2one('qurbani.day', string="Day")
    inventory_product_id = fields.Many2one('product.product', string="Inventory Product")
    slaughter_location_id = fields.Many2one('stock.location', string="Slaughter Location")

    start_time = fields.Float('Start Time')
    end_time = fields.Float('End Time')

    video = fields.Binary('Video')
    image = fields.Binary('Image')

    name = fields.Char('Name', default="New")
    video_file_name = fields.Char('Video File Name')
    image_file_name = fields.Char('Image File Name')

    state = fields.Selection(selection=state_selection, string="State", compute="_set_state", default='available', store=True)

    slot_full = fields.Integer('Slot Full')

    qurbani_cow_slaughter_line = fields.One2many('qurbani.cow.slaughter.line', 'qurbani_cow_slaughter_id', string="Qurbani Cow Slaughter Line")


    @api.depends('slot_full')
    def _set_state(self):
        for rec in self:
            if rec.slot_full == 7:
                rec.state = 'full'

    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            slaughter_location = self.env['stock.location'].browse(vals['slaughter_location_id'])

            vals['name'] = f'Cow - {str(slaughter_location.cow_sequence_number).zfill(5)}'

            slaughter_location.cow_sequence_number += 1

        return super(QurbaniCowSlaughter, self).create(vals)
    
    def action_transfer(self):
        return {
            'name': _('Transfer Slaughter'),
            'type': 'ir.actions.act_window',
            'res_model': 'transfer.slaughter',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_qurbani_cow_slaughter_id': self.id,
            }
        }
    
    def action_print_report(self):
        for rec in self:
            if rec.slot_full < 7:
                raise ValidationError('Cannot generate an incomplete cow for sluaghter report.')
            
        return self.env.ref('bn_qurbani.qurbani_cow_slaughter_report').report_action(self)