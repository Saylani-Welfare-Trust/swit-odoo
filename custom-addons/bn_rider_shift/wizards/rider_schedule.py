
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

        # 🔹 Get all active key issuances for this rider (NO date filter)
        key_issuances = self.env['key.issuance'].search([
            ('rider_id', '=', employee.id),
            ('state', 'in', ['issued', 'overdue']),
        ])

        if not key_issuances:
            raise UserError(_("No active keys found for this rider."))

        # 🔹 Get lot_ids
        lot_ids = key_issuances.mapped('lot_id')

        # 🔹 Fetch existing collections (NO date restriction)
        existing_collections = self.env['rider.collection'].search([
            ('rider_id', '=', employee.id),
            ('lot_id', 'in', lot_ids.ids),
            ('state', 'not in', ['pending', 'donation_submit', 'paid']),
        ])

        existing_lot_ids = existing_collections.mapped('lot_id').ids

        # 🔹 Add existing collections
        for record in existing_collections:
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

        # 🔹 Find missing lot_ids
        missing_lot_ids = list(set(lot_ids.ids) - set(existing_lot_ids))

        # 🔹 Avoid duplicates (NO date restriction)
        finalized_missing_lot_ids = []

        for lot_id in missing_lot_ids:
            already_exists = self.env['rider.collection'].search([
                ('lot_id', '=', lot_id),
                ('rider_id', '=', employee.id),
                ('state', 'not in', ['pending', 'donation_submit', 'paid']),
            ], limit=1)

            if not already_exists:
                finalized_missing_lot_ids.append(lot_id)

        # 🔹 Create new collections
        boxes = self.env['donation.box.registration.installation'].search([
            ('lot_id', 'in', finalized_missing_lot_ids),
            ('status', '!=', 'close')
        ])

        for box in boxes:
            collection = self.env['rider.collection'].create({
                'rider_id': employee.id,
                'date': fields.Date.today(),  # optional (can remove if not needed)
                'donation_box_registration_installation_id': box.id,
            })

            line_vals.append((0, 0, {
                'rider_collection_id': collection.id,
                'date': collection.date,
                'state': collection.state,
                'donation_box_registration_installation_id': box.id,
            }))

        # 🔹 Build wizard
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