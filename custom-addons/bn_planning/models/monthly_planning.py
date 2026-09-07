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

    # ───── Button: actually create the lines (clears and recreates) ─────
    def action_generate_days(self):
        for rec in self:
            if not rec.month or not rec.year:
                raise ValidationError("Please select a month and year first.")

            # Delete existing lines from ALL tabs
            rec.kitchen_line_ids.unlink()
            rec.madaris_line_ids.unlink()
            rec.medical_line_ids.unlink()
            rec.livestock_line_ids.unlink()
            rec.food_line_ids.unlink()
            rec.ration_line_ids.unlink()
            rec.meat_line_ids.unlink()

            days = calendar.monthrange(rec.year, list(dict(MONTH_SELECTION).keys()).index(rec.month) + 1)[1]
            month_num = list(dict(MONTH_SELECTION).keys()).index(rec.month) + 1

            for day in range(1, days + 1):
                date_obj = datetime(rec.year, month_num, day).date()
                # Create lines for each model
                self.env['monthly.planning.kitchen'].create({
                    'monthly_planning_id': rec.id,
                    'date': date_obj,
                    'quantity': 0.0,
                })
                self.env['monthly.planning.madaris'].create({
                    'monthly_planning_id': rec.id,
                    'date': date_obj,
                    'quantity': 0.0,
                })
                self.env['monthly.planning.medical'].create({
                    'monthly_planning_id': rec.id,
                    'date': date_obj,
                    'quantity': 0.0,
                })
                self.env['monthly.planning.livestock'].create({
                    'monthly_planning_id': rec.id,
                    'date': date_obj,
                    'quantity': 0.0,
                })
                # NEW lines
                self.env['monthly.planning.food'].create({
                    'monthly_planning_id': rec.id,
                    'date': date_obj,
                    'quantity': 0.0,
                })
                self.env['monthly.planning.ration'].create({
                    'monthly_planning_id': rec.id,
                    'date': date_obj,
                    'quantity': 0.0,
                })
                self.env['monthly.planning.meat'].create({
                    'monthly_planning_id': rec.id,
                    'date': date_obj,
                    'quantity': 0.0,
                })

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_generate_daily_planning(self):
        """
        For each day and each tab, create (or update) a Daily Planning record
        for that specific tab only.
        """
        total_created = 0
        total_updated = 0

        # Map tab names to their One2many field names
        tab_map = {
            'kitchen': 'kitchen_line_ids',
            'madaris': 'madaris_line_ids',
            'medical': 'medical_line_ids',
            'livestock': 'livestock_line_ids',
            'food': 'food_line_ids',
            'ration': 'ration_line_ids',
            'meat': 'meat_line_ids',
        }

        for rec in self:
            if not rec.month or not rec.year:
                raise ValidationError("Please select a month and year first.")

            month_num = [m[0] for m in MONTH_SELECTION].index(rec.month) + 1
            days_in_month = calendar.monthrange(rec.year, month_num)[1]

            for day in range(1, days_in_month + 1):
                date_obj = datetime(rec.year, month_num, day).date()

                for tab_key, field_name in tab_map.items():
                    lines = getattr(rec, field_name).filtered(
                        lambda l, d=date_obj: l.date == d and l.product_id
                    )

                    if not lines:
                        continue

                    # Build line commands for this tab
                    line_vals = [(0, 0, {
                        'product_id': line.product_id.id,
                        'quantity': line.quantity,
                    }) for line in lines]

                    # Search for existing daily planning for this tab + day
                    existing = self.env['daily.planning'].search([
                        ('monthly_planning_id', '=', rec.id),
                        ('date', '=', date_obj),
                        ('source_tab', '=', tab_key),
                    ], limit=1)

                    try:
                        if existing:
                            existing.write({
                                'daily_planning_line_ids': [(5, 0, 0)] + line_vals
                            })
                            total_updated += 1
                        else:
                            self.env['daily.planning'].create({
                                'monthly_planning_id': rec.id,
                                'day': day,
                                'source_tab': tab_key,          # actual tab name
                                'type': 'distribution',
                                'daily_planning_line_ids': line_vals,
                            })
                            total_created += 1
                    except Exception as e:
                        raise ValidationError(f"Error generating Daily Planning for {date_obj} ({tab_key}):\n{str(e)}")

        message = f"Daily Planning created: {total_created} new, updated: {total_updated}."
        if total_created == 0 and total_updated == 0:
            message = "No products found in any tab for any day. Nothing generated."

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': message,
                'type': 'success',
                'sticky': False,
            }
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