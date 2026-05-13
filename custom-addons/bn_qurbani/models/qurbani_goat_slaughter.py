from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class QurbaniGoatSlaughter(models.Model):
    _name = 'qurbani.goat.slaughter'
    _description = "Qurbani Goat Slaughter"


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

    product_id = fields.Many2one('product.product', string="Product")

    qurbani_order_no = fields.Char('QO No.')
    qurbani_order_line_no = fields.Char('QOL No.')
    hissa_name = fields.Char('Hissa Name')


    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            slaughter_location = self.env['stock.location'].browse(vals['slaughter_location_id'])

            vals['name'] = f'Goat - {str(slaughter_location.goat_sequence_number).zfill(5)}'

            slaughter_location.goat_sequence_number += 1

        return super(QurbaniGoatSlaughter, self).create(vals)
    
    def action_transfer(self):
        return {
            'name': _('Transfer Slaughter'),
            'type': 'ir.actions.act_window',
            'res_model': 'transfer.slaughter',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_qurbani_goat_slaughter_id': self.id,
                'default_type': 'goat',
                'default_option': 'hole',
            }
        }
    
    def action_print_report(self):
        return self.env.ref('bn_qurbani.qurbani_goat_slaughter_report').report_action(self)