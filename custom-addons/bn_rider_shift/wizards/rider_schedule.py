from odoo import fields, models, api, _
from odoo.exceptions import UserError


class RiderSchedule(models.TransientModel):
    _name = 'rider.schedule'
    _description = 'Rider Schedule'

    rider_schedule_line_ids = fields.One2many('rider.schedule.line', 'rider_schedule_id', string="Rider Schedule Lines")

    name = fields.Char('Name', default="NEW")


    @api.model
    def create(self, vals):
        if vals.get('name', _('NEW')) == _('NEW'):
            vals['name'] = self.env['ir.sequence'].next_by_code('rider_schedule') or _('New')
        
        return super(RiderSchedule, self).create(vals)

    def action_check_shift(self):
        employee = self.env.user.employee_id

        if not employee:
            raise UserError(_("No employee linked to current user."))

        today = fields.Date.today()

        unfinished_states = ['donation_not_collected', 'donation_collected']

        # =========================================================
        # 🔥 FETCH ONLY UNFINISHED rider.collection
        # =========================================================
        collections_to_show = self.env['rider.collection'].search([
            ('rider_id', '=', employee.id),
            ('state', 'in', unfinished_states),
            ('date', '<=', today),
        ], order="date desc")

        line_vals = []

        for record in collections_to_show:
            line_vals.append((0, 0, {
                'rider_collection_id': record.id,
                'rider_id': record.rider_id.id,
                'date': record.date,
                'state': record.state,
                'submission_time': record.submission_time,
                'donation_box_registration_installation_id': record.donation_box_registration_installation_id.id,
                'amount': record.amount,
                'counterfeit_notes': record.counterfeit_notes,
                'remarks': record.remarks,
            }))

        # =========================================================
        # 🔹 CREATE WIZARD
        # =========================================================
        rider_schedule = self.env['rider.schedule'].create({
            'rider_schedule_line_ids': line_vals
        })

        self.unlink()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'rider.schedule',
            'view_mode': 'form',
            'view_id': self.env.ref('bn_rider_shift.rider_schedule_view_form').id,
            'res_id': rider_schedule.id,
            'target': 'current'
        }