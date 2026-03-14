from odoo import models, fields, api


month_selection = [
    ('jan', 'Januray'),
    ('feb', 'February'),
    ('mar', 'March'),
    ('apr', 'April'),
    ('may', 'May'),
    ('jun', 'June'),
    ('jul', 'July'),
    ('aug', 'Auguest'),
    ('aug', 'August'),
    ('sep', 'September'),
    ('nov', 'November'),
    ('dec', 'December'),
]


class MeatManagement(models.Model):
    _name = 'meat.management'
    _description = "Meat Management"
    _inherit = ["mail.thread", "mail.activity.mixin"]


    month = fields.Selection(selection=month_selection, string="Month")

    name = fields.Char('Name', compute="_set_name", store=True)

    excess_livestock_qty = fields.Float('Excess Livestock', compute="_compute_totals", store=True)
    total_livestock_qty = fields.Float('Total Livestock Confirmed', compute='_compute_totals', store=True)
    total_raw_meat_qty = fields.Float('Total Raw Meat Required (kg)', compute="_compute_totals", store=True)

    kitchen_meat_management_line_ids = fields.One2many('kitchen.meat.management', 'meat_management_id', string="Kitchen Meat Management Lines")
    madaris_meat_management_line_ids = fields.One2many('madaris.meat.management', 'meat_management_id', string="Madaris Meat Management Lines")
    medical_meat_management_line_ids = fields.One2many('medical.meat.management', 'meat_management_id', string="Medical Meat Management Lines")
    livestock_meat_management_line_ids = fields.One2many('livestock.meat.management', 'meat_management_id', string="Livestock Meat Management Lines")


    @api.depends(
        'kitchen_meat_management_line_ids.quantity',
        'madaris_meat_management_line_ids.quantity',
        'medical_meat_management_line_ids.quantity',
        'livestock_meat_management_line_ids.quantity'
    )
    def _compute_totals(self):
        for rec in self:
            kitchen_meat_management = sum(r.quantity for r in rec.kitchen_meat_management_line_ids)
            madaris_meat_management = sum(r.quantity for r in rec.madaris_meat_management_line_ids)
            medical_meat_management = sum(r.quantity for r in rec.medical_meat_management_line_ids)
            
            rec.total_livestock_qty = sum(r.quantity for r in rec.livestock_meat_management_line_ids)

            rec.total_raw_meat_qty = kitchen_meat_management + madaris_meat_management + medical_meat_management
            rec.excess_livestock_qty = max(rec.total_livestock_qty - (rec.total_raw_meat_qty / 5), 0)

    @api.depends('month', 'excess_livestock_qty', 'total_raw_meat_qty', 'total_livestock_qty')
    def _set_name(self):
        for rec in self:
            rec.name = f'{rec.month} - {rec.excess_livestock_qty} - {rec.total_raw_meat_qty} - {rec.total_livestock_qty}'