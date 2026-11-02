from odoo import models, fields, api


class DonationHomeService(models.Model):
    _inherit = 'donation.home.service'


    qurbani_order_id = fields.Many2one('qurbani.order', string='Qurbani Order')

    favor = fields.Char('Favor')


    def action_cancel(self):
        res = super().action_cancel()
        # free the hissa booked for the qurbani of a cancelled home service
        self.qurbani_order_id._release_booked_hissa()
        return res

    @api.model
    def create_dhs_record(self, data):
        result = super().create_dhs_record(data)
        if not result or result.get('status') != 'success':
            return result

        dhs = self.browse(result['id'])
        if data.get('favor'):
            dhs.favor = data['favor']

        params = self.env['ir.config_parameter'].sudo()
        if params.get_param('enable_qurbani', default=False):
            dhs.qurbani_order_id = self.env['qurbani.order']._book_qurbani(data)

        return result
