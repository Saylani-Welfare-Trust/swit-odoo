from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import logging


_logger = logging.getLogger(__name__)


class MonthlyPlanning(models.Model):
    _name = 'monthly.planning'
    _description = 'Monthly Planning'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ─── Header fields ─────────────────────────────────────
    name = fields.Char(
        string='Name',
        required=True,
        tracking=True,
        help='Give the plan a descriptive name, e.g. "January 2026 – Kitchen Plan".',
    )
    from_date = fields.Date(
        string='From Date',
        required=True,
        default=lambda self: fields.Date.today() + timedelta(days=1),
        tracking=True,
    )
    to_date = fields.Date(
        string='To Date',
        required=True,
        default=lambda self: fields.Date.today() + timedelta(days=30),
        tracking=True,
    )

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

    created_by = fields.Many2one(
        'res.users',
        string='Created By',
        default=lambda self: self.env.user,
        readonly=True,
        copy=False,
        help='User who created this record.',
    )
    enabled_tabs = fields.Char(
        string='Enabled Pages',
        compute='_compute_enabled_tabs',
        store=True,
    )

    @api.depends(
        'planning_type_id',
        'planning_type_id.kitchen',
        'planning_type_id.madaris',
        'planning_type_id.medical',
        'planning_type_id.livestock',
        'planning_type_id.food',
        'planning_type_id.ration',
        'planning_type_id.meat',
    )
    def _compute_enabled_tabs(self):
        label_map = [
            ('kitchen',   'Kitchen'),
            ('madaris',   'Madaris'),
            ('medical',   'Medical'),
            ('livestock', 'Livestock'),
            ('food',      'Food'),
            ('ration',    'Ration'),
            ('meat',      'Meat'),
        ]
        for rec in self:
            if not rec.planning_type_id:
                rec.enabled_tabs = ''
                continue
            names = [
                label for field, label in label_map
                if getattr(rec.planning_type_id, field, False)
            ]
            rec.enabled_tabs = ', '.join(names)

    # ─── State ─────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ('draft',  'Draft'),
            ('active', 'Active'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        copy=False,
    )

    # ─── Lock flag (auto, based on to_date) ────────────────
    is_locked = fields.Boolean(
        string='Locked (Past Period)',
        compute='_compute_is_locked',
        store=True,
        help='Automatically true when the planning period has ended '
             '(To Date is today or earlier). Locked plans cannot be edited '
             'or deleted, and lines cannot be modified.',
    )

    @api.depends('to_date')
    def _compute_is_locked(self):
        today = fields.Date.today()
        for rec in self:
            # Never lock a record that hasn't been saved yet — the form
            # starts with today's date, which would otherwise mark it locked.
            if not rec.id:
                rec.is_locked = False
                continue
            # Lock only when the period is strictly over (to_date in the past).
            # A period ending today is still editable today.
            rec.is_locked = bool(rec.to_date and rec.to_date < today)

    # ─── Default destination ──────────────────────────────
    @api.model
    def _default_location_dest(self):
        employee = self.env['hr.employee'].search(
            [('user_id', '=', self.env.uid)], limit=1
        )

        if employee and employee.analytic_account_id:
            location = self.env['stock.location'].search(
                [
                    ('analytic_account_id', '=', employee.analytic_account_id.id),
                    ('usage', 'in', ['internal']),
                ],
                limit=1,
            )
            if location:
                return location.id

        fallback = self.env.ref(
            'stock.stock_location_stock', raise_if_not_found=False
        )
        return fallback.id if fallback else False

    location_dest_id = fields.Many2one(
        'stock.location',
        string='Destination Location',
        domain="[('usage', 'in', ['internal'])]",
        default=lambda self: self._default_location_dest(),
        help='Auto-filled from the analytical account (Branch Location) '
             'tagged on the employee linked to the current user.',
    )

    show_kitchen = fields.Boolean(
        related='planning_type_id.kitchen', string='Kitchen', store=False,
    )
    show_madaris = fields.Boolean(
        related='planning_type_id.madaris', string='Madaris', store=False,
    )
    show_medical = fields.Boolean(
        related='planning_type_id.medical', string='Medical', store=False,
    )
    show_livestock = fields.Boolean(
        related='planning_type_id.livestock', string='Livestock', store=False,
    )
    show_food = fields.Boolean(
        related='planning_type_id.food', string='Food', store=False,
    )
    show_ration = fields.Boolean(
        related='planning_type_id.ration', string='Ration', store=False,
    )
    show_meat = fields.Boolean(
        related='planning_type_id.meat', string='Meat', store=False,
    )

    # ─── Constraints ──────────────────────────────────────
    @api.constrains('from_date', 'to_date')
    def _check_date_range(self):
        for rec in self:
            if rec.from_date and rec.to_date and rec.from_date > rec.to_date:
                raise ValidationError(
                    "'From Date' must be earlier than or equal to 'To Date'."
                )

    @api.constrains('from_date')
    def _check_no_backdate_on_create(self):
        """Block creating a NEW Monthly Planning with a From Date in the past.

        Only fires on freshly-created records (rec._origin.id is None);
        editing an existing record is not affected.
        """
        today = fields.Date.today()
        for rec in self:
            if rec._origin.id is None and rec.from_date and rec.from_date < today:
                raise ValidationError(
                    "You cannot create a Monthly Planning with a 'From Date' "
                    "in the past.\nEarliest allowed date: %s." % today
                )

    # ─── Helpers ──────────────────────────────────────────
    def _get_line_commands_for_days(self):
        """Return a list of (0, 0, values) for each day between from_date and to_date."""
        self.ensure_one()
        commands = []
        if not self.from_date or not self.to_date:
            return commands
        delta = (self.to_date - self.from_date).days
        for i in range(delta + 1):
            date_obj = self.from_date + timedelta(days=i)
            commands.append((0, 0, {
                'date': date_obj,
                'quantity': 0.0,
            }))
        return commands

    def is_date_in_range(self, date_val):
        """Return True if `date_val` falls within [from_date, to_date] (inclusive)."""
        self.ensure_one()
        if not date_val or not self.from_date or not self.to_date:
            return False
        return self.from_date <= date_val <= self.to_date

    # ─── Actions ──────────────────────────────────────────
    def action_open_import_wizard(self):
        self.ensure_one()
        if self.is_locked:
            raise ValidationError(
                "This Monthly Planning is locked and cannot be modified."
            )
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

    def action_set_active(self):
        for rec in self:
            if rec.is_locked:
                raise ValidationError(
                    "This Monthly Planning is locked and cannot be modified."
                )
            if not rec.planning_type_id:
                raise ValidationError(
                    "Please select a Planning Type before activating."
                )
            rec.state = 'active'

    def action_set_draft(self):
        for rec in self:
            if rec.is_locked:
                raise ValidationError(
                    "This Monthly Planning is locked and cannot be modified."
                )
            rec.state = 'draft'

    # ─── Lock guards on write / unlink ────────────────────
    def write(self, vals):
        for rec in self:
            if rec.is_locked:
                allowed = {'state'}
                if not set(vals.keys()).issubset(allowed):
                    raise ValidationError(
                        "This Monthly Planning is locked (period ended on %s). "
                        "Editing is not allowed." % rec.to_date
                    )
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.is_locked:
                raise ValidationError(
                    "This Monthly Planning cannot be deleted because its "
                    "period ended on %s." % rec.to_date
                )
        return super().unlink()


# ─── Base class for line models ──────────────────────────────
class MonthlyPlanningLineBase(models.AbstractModel):
    _name = 'monthly.planning.line.base'
    _description = 'Base Line for Monthly Planning'

    monthly_planning_id = fields.Many2one('monthly.planning', string="Monthly Planning")
    date = fields.Date(
        string="Date",
        required=True,
        default=lambda self: self._default_line_date(),
    )

    @api.model
    def _default_line_date(self):
        """Default to the parent plan's From Date (or today if there is none)."""
        parent_id = self.env.context.get('default_monthly_planning_id')
        if parent_id:
            parent = self.env['monthly.planning'].browse(parent_id)
            if parent.from_date:
                return parent.from_date
        return fields.Date.today()
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

    @api.constrains('quantity', 'product_id')
    def _check_active_plan(self):
        for rec in self:
            if rec.monthly_planning_id.state == 'active':
                raise ValidationError(
                    "This Monthly Planning is Active. Set it back to Draft to edit lines."
                )

    def write(self, vals):
        for rec in self:
            if rec.monthly_planning_id.is_locked:
                raise ValidationError(
                    "This Monthly Planning is locked (period ended on %s). "
                    "Lines cannot be modified."
                    % rec.monthly_planning_id.to_date
                )
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.monthly_planning_id.is_locked:
                raise ValidationError(
                    "This Monthly Planning is locked (period ended on %s). "
                    "Lines cannot be deleted."
                    % rec.monthly_planning_id.to_date
                )
        return super().unlink()


# ─── Concrete models ─────────────────────────────────────────
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