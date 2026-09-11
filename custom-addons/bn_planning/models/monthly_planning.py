from odoo import models, fields, api
from odoo.exceptions import ValidationError
import calendar
from datetime import datetime
import logging
    

_logger = logging.getLogger(__name__)

MONTH_SELECTION = [
    ('jan', 'January'),
    ('feb', 'February'),
    ('mar', 'March'),
    ('apr', 'April'),
    ('may', 'May'),
    ('jun', 'June'),
    ('jul', 'July'),
    ('aug', 'August'),
    ('sep', 'September'),
    ('oct', 'October'),
    ('nov', 'November'),
    ('dec', 'December'),
]

class MonthlyPlanning(models.Model):
    _name = 'monthly.planning'
    _description = 'Monthly Planning'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    month = fields.Selection(selection=MONTH_SELECTION, string="Month", required=True)
    year = fields.Integer(string="Year", default=lambda self: datetime.today().year, required=True)
    name = fields.Char('Name', compute='_compute_name', store=True)

    # Existing tabs
    kitchen_line_ids = fields.One2many('monthly.planning.kitchen', 'monthly_planning_id', string="Kitchen")
    madaris_line_ids = fields.One2many('monthly.planning.madaris', 'monthly_planning_id', string="Madaris")
    medical_line_ids = fields.One2many('monthly.planning.medical', 'monthly_planning_id', string="Medical")
    livestock_line_ids = fields.One2many('monthly.planning.livestock', 'monthly_planning_id', string="Livestock")

    # NEW tabs
    food_line_ids = fields.One2many('monthly.planning.food', 'monthly_planning_id', string="Food")
    ration_line_ids = fields.One2many('monthly.planning.ration', 'monthly_planning_id', string="Ration")
    meat_line_ids = fields.One2many('monthly.planning.meat', 'monthly_planning_id', string="Meat")

    planning_type_id = fields.Many2one(
    'planning.type',
    string='Planning Type',
    required=True,
    tracking=True,
    )

    show_kitchen = fields.Boolean(
        related='planning_type_id.kitchen',
        string='Kitchen',
        store=False,
    )

    show_madaris = fields.Boolean(
        related='planning_type_id.madaris',
        string='Madaris',
        store=False,
    )

    show_medical = fields.Boolean(
        related='planning_type_id.medical',
        string='Medical',
        store=False,
    )

    show_livestock = fields.Boolean(
        related='planning_type_id.livestock',
        string='Livestock',
        store=False,
    )

    show_food = fields.Boolean(
        related='planning_type_id.food',
        string='Food',
        store=False,
    )

    show_ration = fields.Boolean(
        related='planning_type_id.ration',
        string='Ration',
    )

    show_meat = fields.Boolean(
        related='planning_type_id.meat',
        string='Meat',
        store=False,
    )

    @api.depends('month', 'year')
    def _compute_name(self):
        for rec in self:
            rec.name = f"{rec.month or '?'} {rec.year}"

    # ───── Helper to build virtual line commands ─────
    def _get_line_commands_for_days(self, days):
        """Return a list of (0, 0, values) for each day."""
        commands = []
        for day in range(1, days + 1):
            date_obj = datetime(self.year, list(dict(MONTH_SELECTION).keys()).index(self.month) + 1, day).date()
            commands.append((0, 0, {
                'date': date_obj,
                'quantity': 0.0,
            }))
        return commands


    def action_open_import_wizard(self):
        self.ensure_one()
        if not self.planning_type_id:
            raise ValidationError("Please select a Planning Type first.")
        return {
            'type': 'ir.actions.act_window',
            'name': 'Import Monthly Planning from Excel',
            'res_model': 'import.monthly.planning.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_monthly_planning_id': self.id},
        }

# ─── Base class for line models ──────────────────────────────
class MonthlyPlanningLineBase(models.AbstractModel):
    _name = 'monthly.planning.line.base'
    _description = 'Base Line for Monthly Planning'

    monthly_planning_id = fields.Many2one('monthly.planning', string="Monthly Planning")
    date = fields.Date(
        string="Date",
        required=True,
        default=fields.Date.today
    )
    product_id = fields.Many2one('product.product', string="Product")
    quantity = fields.Float(string="Quantity", required=True, default=0.0)
    on_hand_qty = fields.Float(string='On Hand Quantity', compute='_compute_on_hand_qty')

    @api.depends('product_id')
    def _compute_on_hand_qty(self):
        source_loc = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
        for rec in self:
            if rec.product_id and source_loc:
                rec.on_hand_qty = rec.product_id.with_context(
                    location=source_loc.id
                ).qty_available
            else:
                rec.on_hand_qty = 0.0


# ─── Concrete models (existing + new) ──────────────────────────
class MonthlyPlanningKitchen(models.Model):
    _name = 'monthly.planning.kitchen'
    _inherit = 'monthly.planning.line.base'
    _description = 'Monthly Planning – Kitchen Line'

class MonthlyPlanningMadaris(models.Model):
    _name = 'monthly.planning.madaris'
    _inherit = 'monthly.planning.line.base'
    _description = 'Monthly Planning – Madaris Line'

class MonthlyPlanningMedical(models.Model):
    _name = 'monthly.planning.medical'
    _inherit = 'monthly.planning.line.base'
    _description = 'Monthly Planning – Medical Line'

class MonthlyPlanningLivestock(models.Model):
    _name = 'monthly.planning.livestock'
    _inherit = 'monthly.planning.line.base'
    _description = 'Monthly Planning – Livestock Line'
    location_id = fields.Many2one('stock.location', string="Location")

# NEW models
class MonthlyPlanningFood(models.Model):
    _name = 'monthly.planning.food'
    _inherit = 'monthly.planning.line.base'
    _description = 'Monthly Planning – Food Line'

class MonthlyPlanningRation(models.Model):
    _name = 'monthly.planning.ration'
    _inherit = 'monthly.planning.line.base'
    _description = 'Monthly Planning – Ration Line'

class MonthlyPlanningMeat(models.Model):
    _name = 'monthly.planning.meat'
    _inherit = 'monthly.planning.line.base'
    _description = 'Monthly Planning – Meat Line'