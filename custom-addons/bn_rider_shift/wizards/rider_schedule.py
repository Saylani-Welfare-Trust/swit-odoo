
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
        # today = fields.Date.today()
        employee = self.env.user.employee_id

        # Find today's shift
        rider_shift_obj = self.env['rider.schedule.day'].search([
            ('rider_shift_id.rider_id', '=', employee.id),
            # ('date', '=', today)
        ])
        if not rider_shift_obj:
            raise UserError(_("No shift found for today. Please check your schedule."))

        line_vals = []
        keys=[]
        # raise UserError(str(rider_shift_obj.read())+" --------------- "+str(employee.id))
        for obj in rider_shift_obj:
            key_ids = self.env['key.issuance'].search([
                # ('key_id', '=', 33922),
                ('key_id', 'in', obj.key_bunch_id.key_ids.ids),
                ('state', 'in', ['issued', 'overdue']),
                # ('issue_date', '<=', obj.date),
            ])

            keys.append(key_ids.mapped('key_name'))

            # raise UserError(str(key_ids.mapped('key_name'))+" --------------- "+str(obj.key_bunch_id.name)+" --------------- "+str(obj.date))
            lot_ids = key_ids.mapped('lot_id')
            # lot_ids = obj.key_bunch_id.key_ids.filtered(lambda k:k.state == 'issued').mapped('lot_id')

            # 🔹 Fetch existing collections for these lot_ids
            existing_collections = self.env['rider.collection'].search([
                ('rider_id', '=', employee.id),
                ('date', '=', obj.date),
                ('is_complain_generated', '=', False),
                # ('date', '<=', today),
                ('lot_id', 'in', lot_ids.ids),
                ('state', 'not in', ['pending', 'donation_submit', 'paid']),
            ])

            # Get already existing lot_ids
            existing_lot_ids = existing_collections.mapped('lot_id').ids

            # 🔹 Add existing collections to the lines
            for record in existing_collections:
                line_vals.append((0, 0, {
                    'rider_collection_id': record.id,
                    'rider_id': record.rider_id.id,
                    'day': record.day,
                    'date': record.date,
                    'state': record.state,
                    'submission_time': record.submission_time,
                    'donation_box_registration_installation_id': record.donation_box_registration_installation_id.id,
                    'amount': record.amount,
                    'counterfeit_notes': record.counterfeit_notes,
                    'remarks': record.remarks,
                }))

            # 🔹 Create new collections only for missing lot_ids
            missing_lot_ids = list(set(lot_ids.ids) - set(existing_lot_ids))
            finalized_missing_lot_ids = []

            # raise UserError(str(missing_lot_ids)+" --------------- "+str(lot_ids.ids)+" --------------- "+str(existing_lot_ids))

            if missing_lot_ids:
                for missing_lot_id in missing_lot_ids:
                    # if not self.env['rider.collection'].search([('lot_id', '=', missing_lot_id), ('rider_id', '=', employee.id), ('date', '=', today)]):
                    # if not self.env['rider.collection'].search([('lot_id', '=', missing_lot_id), ('rider_id', '=', employee.id), ('date', '=', obj.date)]):
                    if not self.env['rider.collection'].search([('lot_id', '=', missing_lot_id), ('rider_id', '=', employee.id)]):
                        finalized_missing_lot_ids.append(missing_lot_id)

                boxes = self.env['donation.box.registration.installation'].search([
                    ('lot_id', 'in', finalized_missing_lot_ids),
                    ('status', '!=', 'close')
                ])

                for box in boxes:
                    collection = self.env['rider.collection'].create({
                        'rider_id': employee.id,
                        'day': obj.day,
                        'date': obj.date,
                        'donation_box_registration_installation_id': box.id,
                    })

                    line_vals.append((0, 0, {
                        'rider_collection_id': collection.id,
                        'day': collection.day,
                        'date': collection.date,
                        'state': collection.state,
                        'donation_box_registration_installation_id': box.id,
                        # 'amount': collection.amount,
                        # 'foreign_notes': collection.foreign_notes,
                        # 'counterfeit_notes': collection.counterfeit_notes,
                    }))

        # raise UserError(str(keys)+" --------------- ")

        # ✅ Build wizard
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