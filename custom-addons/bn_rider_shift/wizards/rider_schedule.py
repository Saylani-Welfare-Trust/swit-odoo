
from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError


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

        line_vals = []

        # ✅ ONLY these should appear in schedule
        active_states = ['donation_not_collected', 'donation_collected']

        # 🔹 Get active key issuances
        key_issuances = self.env['key.issuance'].search([
            ('rider_id', '=', employee.id),
            ('state', 'in', ['issued', 'overdue']),
        ])

        if not key_issuances:
            raise UserError(_("No active keys found for this rider."))

        # 🔹 Get lot_ids
        lot_ids = key_issuances.mapped('lot_id').ids

        # 🔥 STEP 1: Fetch ONLY active state records for display
        active_collections = self.env['rider.collection'].search([
            ('rider_id', '=', employee.id),
            ('lot_id', 'in', lot_ids),
            ('state', 'in', active_states),
        ])

        # 🔹 Add ONLY active records to wizard
        for record in active_collections:
            line_vals.append((0, 0, {
                'rider_collection_id': record.id,
                'rider_id': record.rider_id.id if record.rider_id else False,
                'date': record.date,
                'state': record.state,
                'submission_time': record.submission_time,
                'donation_box_registration_installation_id':
                    record.donation_box_registration_installation_id.id
                    if record.donation_box_registration_installation_id else False,
                'amount': record.amount,
                'counterfeit_notes': record.counterfeit_notes,
                'remarks': record.remarks,
            }))

        # 🔥 STEP 2: Find missing lots (NO record exists in ANY state)
        missing_lot_ids = list(set(lot_ids) - set(
            self.env['rider.collection'].search([
                ('rider_id', '=', employee.id),
                ('lot_id', 'in', lot_ids),
            ]).mapped('lot_id').ids
        ))

        # 🔹 Get boxes for missing lots
        boxes = self.env['donation.box.registration.installation'].search([
            ('lot_id', 'in', missing_lot_ids),
            ('status', '!=', 'close')
        ])

        # 🔥 STEP 3: Create only truly missing records
        for box in boxes:
            collection = self.env['rider.collection'].create({
                'rider_id': employee.id,
                'date': fields.Date.today(),
                'donation_box_registration_installation_id': box.id,
            })

            line_vals.append((0, 0, {
                'rider_collection_id': collection.id,
                'rider_id': employee.id,
                'date': collection.date,
                'state': collection.state,
                'donation_box_registration_installation_id': box.id,
            }))

        # 🔹 Create schedule
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