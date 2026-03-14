from odoo import fields, models, api


day_selection = [
    ('mon', 'Monday'),
    ('tue', 'Tuesday'),
    ('wed', 'Wednesday'),
    ('thu', 'Thursday'),
    ('fri', 'Friday'),
    ('sat', 'Saturday'),
    ('sun', 'Sunday'),
]

class RiderScheduleDay(models.Model):
    _name = 'rider.schedule.day'
    _description = 'Rider Schedule Day'
    _inherit = ["mail.thread", "mail.activity.mixin"]


    rider_shift_id = fields.Many2one('rider.shift', string="Rider Shift")

    day = fields.Selection(selection=day_selection, string="Day", default='mon')

    date = fields.Date("Date")

    city_id = fields.Many2one('account.analytic.account', string="City")
    zone_id = fields.Many2one('account.analytic.account', string="Zone")
    key_bunch_id = fields.Many2one('key.bunch', string="Key Bunch")
    sub_zone_id = fields.Many2one('sub.zone', string="Sub Zone", tracking=True)

    key_count = fields.Integer('Key Count', compute="_set_key_count")

    name = fields.Char('Name', compute="_set_name")
    
    # New fields as per requirement
    shop_name = fields.Char('Shop Name')
    box_no = fields.Char('Box No')
    contact_person = fields.Char('Contact Person')
    contact_number = fields.Char('Contact Number')
    status = fields.Selection([
        ('donation_not_collected', 'Donation not collected'),
        ('donation_collected', 'Donation collected'),
        ('donation_submit', 'Donation submit'),
        ('pending', 'Pending'),
        ('paid', 'Paid')
    ], string='Status', default='donation_not_collected')
    comments = fields.Text('Comments')
    
    # Amount Collection Fields
    actual_amount = fields.Float('Actual Amount')
    counterfeit_amount = fields.Float('Counterfeit Amount')
    foreign_currency_amount = fields.Float('Foreign Currency Amount')
    
    # Complaint Fields
    complaint_id = fields.Many2one('donation.box.complain.center', string='Complaint')
    has_complaint = fields.Boolean('Has Complaint', compute='_compute_has_complaint', store=True)
    
    @api.depends('complaint_id')
    def _compute_has_complaint(self):
        for record in self:
            record.has_complaint = bool(record.complaint_id)


    @api.depends('day', 'rider_shift_id')
    def _set_name(self):
        for record in self:
            record.name = ''

            if record.rider_shift_id:
                record.name = record.day.title() + ' ' + record.rider_shift_id.name

    def _set_key_count(self):
        for rec in self:
            rec.key_count = len(rec.key_bunch_id.key_ids) or 0

    @api.onchange('date')
    def _onchange_date(self):
        if self.date and self.rider_shift_id:
            start = self.rider_shift_id.start_date
            end = self.rider_shift_id.end_date

            if self.date < fields.Date.today():
                self.date = False
                return {
                    'warning': {
                        'title': "Invalid Date",
                        'message': "You cannot select past dates.",
                    }
                }

            if start and end and (self.date < start or self.date > end):
                self.date = False
                return {
                    'warning': {
                        'title': "Invalid Date",
                        'message': f"Date must be between {start} and {end}.",
                    }
                }
            
    @api.onchange('key_bunch_id')
    def _onchange_key_bunch_id(self):
        for key in self.key_bunch_id.key_ids:
            key.rider_id = self.rider_shift_id.rider_id.id
    
    def action_generate_complaint(self):
        """Open wizard to create a complaint"""
        # Get the lot_id from box_no if exists
        lot_id = False
        if self.box_no:
            lot = self.env['stock.lot'].search([('name', '=', self.box_no)], limit=1)
            if lot:
                lot_id = lot.id
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Generate Complaint',
            'res_model': 'donation.box.complain.center',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_rider_id': self.rider_shift_id.rider_id.id if self.rider_shift_id else False,
                'default_lot_id': lot_id,
            }
        }
    
    def action_view_complaints(self):
        """View all complaints for this rider"""
        domain = []
        if self.rider_shift_id and self.rider_shift_id.rider_id:
            domain = [('rider_id', '=', self.rider_shift_id.rider_id.id)]
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Complaints',
            'res_model': 'donation.box.complain.center',
            'view_mode': 'tree,form',
            'domain': domain,
            'context': {'create': False}
        }