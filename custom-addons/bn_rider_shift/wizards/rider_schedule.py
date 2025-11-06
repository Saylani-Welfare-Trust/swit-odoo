from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class RiderSchedule(models.TransientModel):
    _name = 'rider.schedule'
    _description = 'Rider Schedule'

    rider_schedule_line_ids = fields.One2many('rider.schedule.line', 'rider_schedule_id', string="Rider Schedule Lines")


    def action_check_shift(self):
        today = fields.Date.today()
        employee = self.env.user.employee_id

        # Find today's shift
        rider_shift_obj = self.env['rider.schedule.day'].search([
            ('rider_shift_id.rider_id', '=', employee.id),
            ('date', '=', today)
        ])
        if not rider_shift_obj:
            raise UserError(_("No shift found for today. Please check your schedule."))

        line_vals = []

        # First, check if collections already exist for this rider + date
        existing_collections = self.env['rider.collection'].search([
            ('rider_id', '=', employee.id),
            ('date', '=', today)
        ])

        if existing_collections:
            # ✅ Use existing collections
            for record in existing_collections:
                line_vals.append((0, 0, {
                    'rider_collection_id': record.id,
                    'day': record.day,
                    'date': record.date,
                    'state': record.state,
                    'submission_time': record.submission_time,
                    'shop_name': record.shop_name,
                    'lot_id': record.lot_id.id,
                    'box_location': record.box_location,
                    'contact_person': record.contact_person,
                    'contact_number': record.contact_number,
                    'amount': record.amount,
                }))
        else:
            # ✅ No existing collection → create new from shift
            for obj in rider_shift_obj:
                lot_ids = obj.key_bunch_id.key_ids.mapped('lot_id')
                boxes = self.env['donation.box.registration.installation'].search([('lot_id', 'in', lot_ids.ids)])

                for box in boxes:
                    collection = self.env['rider.collection'].create({
                        'rider_id': employee.id,
                        'day': obj.day,
                        'date': obj.date,
                        'shop_name': box.name,
                        'lot_id': box.lot_id.id,
                        'box_location': box.location,
                        'contact_person': box.contact_person,
                        'contact_number': box.contact_no,
                    })

                    line_vals.append((0, 0, {
                        'rider_collection_id': collection.id,
                        'day': collection.day,
                        'date': collection.date,
                        'state': collection.state,
                        'shop_name': collection.shop_name,
                        'lot_id': collection.lot_id.id,
                        'box_location': collection.box_location,
                        'contact_person': collection.contact_person,
                        'contact_number': collection.contact_number,
                    }))

        # ✅ Build wizard
        rider_scheulde = self.env['rider.schedule'].create({
            'rider_schedule_line_ids': line_vals
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'rider.schedule',
            'view_mode': 'form',
            'view_id': self.env.ref('bn_rider_shift.rider_schedule_view_form').id,
            'res_id': rider_scheulde.id,
            'target': 'new'
        }