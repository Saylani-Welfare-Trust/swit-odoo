from odoo import models, fields, api, SUPERUSER_ID


class DonationBoxesRequestsModel(models.Model):
    _inherit = 'donation.box.requests'

    def action_button_approved(self):
        res = super().action_button_approved()
        gen_donation_req_picking = self.env['ir.config_parameter'].sudo().get_param(
            'donation_box_sp.gen_donation_req_picking')
        if bool(gen_donation_req_picking):
            self._create_donation_picking()
        return res

    def _create_donation_picking(self):
        donation_box_sp_type = self.env['ir.config_parameter'].sudo().get_param(
            'donation_box_sp.donation_box_sp_type')
        if donation_box_sp_type:
            pick_type = self.env['stock.picking.type'].sudo().browse(int(donation_box_sp_type))
            # location_id_sudo = self.env['stock.location'].sudo()
            # location_id_sudo =
            # location_dest_id_sudo = self.env['stock.location'].sudo()
            sm_vals = [(0, 0, {
                'name': 'Stock Move for ' + line.product_id.name,
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity,
                'product_uom': line.product_id.uom_id.id,
                'location_id': pick_type.sudo().default_location_src_id.id,
                'location_dest_id': pick_type.sudo().default_location_dest_id.id

            }) for line in self.donation_box_request_line_ids]
            print('hereeee')
            pick_output = self.env['stock.picking'].create({
                'name': f'/',
                'picking_type_id': pick_type.id,
                'origin': self.name,
                'scheduled_date': self.request_date,
                'location_id': pick_type.default_location_src_id.id,
                'location_dest_id': pick_type.default_location_dest_id.id,
                'move_ids': sm_vals
            })
            self.message_post(
                body=f'A Picking has been created -- {pick_output.name}'
                )
            pick_output.action_confirm()
