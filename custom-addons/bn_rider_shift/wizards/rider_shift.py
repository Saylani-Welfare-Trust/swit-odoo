from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class RiderShiftWizard(models.TransientModel):
    _name = 'rider.shift.wizard'
    _description = 'Rider Shift Wizard'

    rider_shift_wizard_line_ids = fields.One2many('rider.shift.wizard.line', 'rider_shift_wizard_id', string="Rider Shift Wizard Line IDS")


    def action_check_shift(self):
        today = fields.Date.today()
        employee = self.env.user.employee_id

        # Find today's shift
        rider_shift_obj = self.env['schedule.day'].search([
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
                    'city_id': record.city_id.id,
                    'zone_id': record.zone_id.id,
                    'sub_zone_id': record.sub_zone_id.id,
                    'key_location_id': record.key_location_id.id,
                    'state': record.state,
                    'submission_time': record.submission_time,
                    'shop_name': record.shop_name,
                    'box_no': record.box_no,
                    'box_location_name': record.box_location_name,
                    'contact_person': record.contact_person,
                    'contact_number': record.contact_number,
                    'amount': record.amount,
                }))
        else:
            # ✅ No existing collection → create new from shift
            for obj in rider_shift_obj:
                box_nos = obj.key_location_id.key_ids.mapped('box_no')
                box_locations = self.env['donation.box.registration'].search([('lot_id.name', 'in', box_nos)])

                for box_location in box_locations:
                    collection = self.env['rider.collection'].create({
                        'rider_id': employee.id,
                        'day': obj.day,
                        'date': obj.date,
                        'city_id': obj.city_id.id,
                        'zone_id': obj.zone_id.id,
                        'sub_zone_id': obj.sub_zone_id.id,
                        'key_location_id': obj.key_location_id.id,
                        'shop_name': box_location.name,
                        'box_no': box_location.lot_id.name,
                        'box_location_name': box_location.location,
                        'contact_person': box_location.contact_person_name,
                        'contact_number': box_location.contact_no,
                    })

                    line_vals.append((0, 0, {
                        'rider_collection_id': collection.id,
                        'day': collection.day,
                        'date': collection.date,
                        'city_id': collection.city_id.id,
                        'zone_id': collection.zone_id.id,
                        'sub_zone_id': collection.sub_zone_id.id,
                        'key_location_id': collection.key_location_id.id,
                        'state': collection.state,
                        'shop_name': collection.shop_name,
                        'box_no': box_location.lot_id.name,
                        'box_location_name': collection.box_location_name,
                        'contact_person': collection.contact_person,
                        'contact_number': collection.contact_number,
                    }))

        # ✅ Build wizard
        rider_shift_wizard = self.env['rider.shift.wizard'].create({
            'rider_shift_wizard_line_ids': line_vals
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'rider.shift.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('bn_rider_shift.rider_shift_wizard_view_form').id,
            'res_id': rider_shift_wizard.id,
            'target': 'new'
        }
    

day_selection = [
    ('mon', 'Monday'),
    ('tue', 'Tuesday'),
    ('wed', 'Wednesday'),
    ('thu', 'Thursday'),
    ('fri', 'Friday'),
    ('sat', 'Saturday'),
    ('sun', 'Sunday'),
]

state_selection = [
    ('donation_not_collected', 'Donation not collected'),
    ('donation_collected', 'Donation collected'),
    ('donation_submit', 'Donation submit'),
    ('paid', 'Paid')
]


class RiderShiftWizard(models.TransientModel):
    _name = 'rider.shift.wizard.line'
    _description = 'Rider Shift Wizard Line'


    box_no = fields.Char('Box No.')
    shop_name = fields.Char('Shop Name')
    contact_person = fields.Char(string="Contact Person")
    contact_number = fields.Char(string="Contact Number")
    box_location_name = fields.Char(string="Box Location Name")

    rider_collection_id = fields.Many2one('rider.collection', string="Rider Collection ID")
    rider_shift_wizard_id = fields.Many2one('rider.shift.wizard', string="Rider Shift Wizard ID")
    rider_id = fields.Many2one('hr.employee', string="Rider ID", default=lambda self: self.env.user.employee_id.id)
    city_id = fields.Many2one('res.company', string="City ID")
    zone_id = fields.Many2one('res.company', string="Zone ID")
    sub_zone_id = fields.Many2one('sub.zone', string="Sub Zone ID")
    key_location_id = fields.Many2one('key.location', string="Key Location ID", tracking=True)
    
    day = fields.Selection(selection=day_selection, string="Day", default='mon')
    state = fields.Selection(selection=state_selection, string="Status", default='donation_not_collected')
    
    date = fields.Date("Date")

    submission_time = fields.Datetime(string="Submission Date")

    amount = fields.Float('Amount')


    def mark_as_done(self):
        self.state = 'donation_collected'
        self.rider_collection_id.state = 'donation_collected'

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'rider.shift.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('bn_rider_shift.rider_shift_wizard_view_form').id,
            'res_id': self.rider_shift_wizard_id.id,
            'target': 'new'
        }
    
    def mark_as_submit(self):
        self.state = 'donation_submit'
        self.submission_time = fields.Datetime.now()
        self.rider_collection_id.state = 'donation_submit'
        self.rider_collection_id.submission_time = fields.Datetime.now()
        self.rider_collection_id.amount = self.amount

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'rider.shift.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('bn_rider_shift.rider_shift_wizard_view_form').id,
            'res_id': self.rider_shift_wizard_id.id,
            'target': 'new'
        }