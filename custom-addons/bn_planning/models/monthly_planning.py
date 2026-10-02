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
    kitchen_line_ids   = fields.One2many('monthly.planning.kitchen',   'monthly_planning_id', string="Kitchen")
    madaris_line_ids   = fields.One2many('monthly.planning.madaris',   'monthly_planning_id', string="Madaris")
    medical_line_ids   = fields.One2many('monthly.planning.medical',   'monthly_planning_id', string="Medical")
    livestock_line_ids = fields.One2many('monthly.planning.livestock', 'monthly_planning_id', string="Livestock")

    # NEW tabs
    food_line_ids   = fields.One2many('monthly.planning.food',   'monthly_planning_id', string="Food")
    ration_line_ids = fields.One2many('monthly.planning.ration', 'monthly_planning_id', string="Ration")
    meat_line_ids   = fields.One2many('monthly.planning.meat',   'monthly_planning_id', string="Meat")

    planning_type_id = fields.Many2one(
        'planning.type', string='Planning Type', required=True, tracking=True,
    )

    created_by = fields.Many2one(
        'res.users', string='Created By',
        default=lambda self: self.env.user,
        readonly=True, copy=False,
        help='User who created this record.',
    )
    enabled_tabs = fields.Char(
        string='Enabled Pages', compute='_compute_enabled_tabs', store=True,
    )

    @api.depends(
        'planning_type_id',
        'planning_type_id.kitchen', 'planning_type_id.madaris',
        'planning_type_id.medical', 'planning_type_id.livestock',
        'planning_type_id.food',    'planning_type_id.ration',
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
        selection=[('draft', 'Draft'), ('active', 'Active')],
        string='Status', default='draft', required=True,
        tracking=True, copy=False,
    )

    # ─── Lock flag (auto, based on to_date) ────────────────
    is_locked = fields.Boolean(
        string='Locked (Past Period)',
        compute='_compute_is_locked', store=True,
        help='Automatically true when the planning period has ended '
             '(To Date is today or earlier). Locked plans cannot be edited '
             'or deleted, and lines cannot be modified.',
    )

    @api.depends('to_date')
    def _compute_is_locked(self):
        today = fields.Date.today()
        for rec in self:
            if not rec.id:
                rec.is_locked = False
                continue
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

    show_kitchen   = fields.Boolean(related='planning_type_id.kitchen',   string='Kitchen',   store=False)
    show_madaris   = fields.Boolean(related='planning_type_id.madaris',   string='Madaris',   store=False)
    show_medical   = fields.Boolean(related='planning_type_id.medical',   string='Medical',   store=False)
    show_livestock = fields.Boolean(related='planning_type_id.livestock', string='Livestock', store=False)
    show_food      = fields.Boolean(related='planning_type_id.food',      string='Food',      store=False)
    show_ration    = fields.Boolean(related='planning_type_id.ration',    string='Ration',    store=False)
    show_meat      = fields.Boolean(related='planning_type_id.meat',      string='Meat',      store=False)

    source_location_id = fields.Many2one(
        'stock.location',
        string='Source Location',
        domain="[('usage', 'in', ['internal'])]",
        default=lambda self: self._default_source_location(),
        help='Where the stock currently sits. Internal transfers will move '
             'the products from here to the Destination Location.',
    )

    @api.model
    def _default_source_location(self):
        picking_type = self.env.ref(
            'stock.picking_type_internal', raise_if_not_found=False
        )
        if picking_type and picking_type.default_location_src_id:
            return picking_type.default_location_src_id.id
        fallback = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
        return fallback.id if fallback else False
    
    # ─── Internal transfer generation ─────────────────────
    def _create_internal_transfer_for_lines(self, line_list, dest_location):
        """Create ONE internal picking that moves every line in `line_list`
        to `dest_location`. Returns the picking (or an empty recordset).

        `line_list` is a plain Python list of line records — it may hold
        rows from different tab models (kitchen, madaris, medical, …), so
        we can't build a single recordset across them.
        """
        self.ensure_one()

        StockPicking = self.env['stock.picking']
        StockMove    = self.env['stock.move']

        # Drop lines already transferred (safety — idempotent)
        line_list = [l for l in line_list if not l.transfer_picking_id]
        if not line_list:
            return StockPicking

        picking_type = self.env.ref(
            'stock.picking_type_internal', raise_if_not_found=False
        )
        if not picking_type:
            _logger.warning(
                "Cron: 'stock.picking_type_internal' not found. "
                "Enable Storage Locations in Inventory settings."
            )
            return StockPicking

        src_location = self.source_location_id or picking_type.default_location_src_id
        if not src_location or not dest_location:
            _logger.warning(
                "Cron: skipping plan %s — source (%s) or destination (%s) "
                "location missing.", self.name, src_location, dest_location,
            )
            return StockPicking

        # Sort lines for readability
        line_list.sort(
            key=lambda l: (l.product_id.display_name or '',
                           l.date or fields.Date.today())
        )

        picking = StockPicking.create({
            'picking_type_id':  picking_type.id,
            'location_id':      src_location.id,
            'location_dest_id': dest_location.id,
            'origin':           'Monthly Planning: %s' % self.name,
            'scheduled_date':   fields.Datetime.now(),
        })

        move_vals = []
        for line in line_list:
            product = line.product_id
            if not product:
                continue
            uom = product.uom_id
            move_vals.append((0, 0, {
                'name':             product.display_name,
                'product_id':       product.id,
                'product_uom_qty':  line.quantity or 0.0,
                'product_uom':      uom.id,
                'location_id':      src_location.id,
                'location_dest_id': dest_location.id,
                'picking_id':       picking.id,
            }))

        if not move_vals:
            picking.unlink()
            return StockPicking

        StockMove.create(move_vals)

        # Link back so the cron won't pick these lines again
        for line in line_list:
            line.transfer_picking_id = picking.id

        return picking

    @api.model
    def _cron_generate_internal_transfers(self):
        """Daily job: scan Active plans and create one internal transfer
        per plan for all not-yet-transferred lines."""
        o2m_names = (
            'kitchen_line_ids', 'madaris_line_ids', 'medical_line_ids',
            'livestock_line_ids', 'food_line_ids', 'ration_line_ids',
            'meat_line_ids',
        )

        plans = self.search([
            ('state', '=', 'active'),
            ('is_locked', '=', False),
            ('location_dest_id', '!=', False),
        ])

        _logger.info(
            "Cron internal transfers: scanning %d active plan(s).", len(plans)
        )

        created_total = 0
        for plan in plans:
            pending = []
            for o2m_name in o2m_names:
                for line in getattr(plan, o2m_name):
                    if (not line.transfer_picking_id
                            and line.product_id
                            and (line.quantity or 0.0) > 0):
                        pending.append(line)

            if not pending:
                continue

            picking = plan._create_internal_transfer_for_lines(
                pending, plan.location_dest_id
            )
            if picking:
                created_total += 1
                _logger.info(
                    "Cron internal transfers: created %s for plan %s (%d lines).",
                    picking.name, plan.name, len(pending),
                )

        _logger.info(
            "Cron internal transfers: finished. %d picking(s) created.",
            created_total,
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
        today = fields.Date.today()
        for rec in self:
            if rec._origin.id is None and rec.from_date and rec.from_date < today:
                raise ValidationError(
                    "You cannot create a Monthly Planning with a 'From Date' "
                    "in the past.\nEarliest allowed date: %s." % today
                )

    # ─── Helpers ──────────────────────────────────────────
    def _get_line_commands_for_days(self):
        self.ensure_one()
        commands = []
        if not self.from_date or not self.to_date:
            return commands
        delta = (self.to_date - self.from_date).days
        for i in range(delta + 1):
            date_obj = self.from_date + timedelta(days=i)
            commands.append((0, 0, {'date': date_obj, 'quantity': 0.0}))
        return commands

    def is_date_in_range(self, date_val):
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
            'view_mode': 'form', 'target': 'new',
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

            o2m_names = (
                'kitchen_line_ids', 'madaris_line_ids', 'medical_line_ids',
                'livestock_line_ids', 'food_line_ids', 'ration_line_ids',
                'meat_line_ids',
            )
            for o2m_name in o2m_names:
                for line in getattr(rec, o2m_name):
                    line.planned_qty = line.quantity
                    if rec.location_dest_id:
                        line.location_id = rec.location_dest_id

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
        string="Date", required=True,
        default=lambda self: self._default_line_date(),
    )

    plan_from_date = fields.Date(
        related='monthly_planning_id.from_date',
        string='Plan From Date', store=False,
    )
    plan_to_date = fields.Date(
        related='monthly_planning_id.to_date',
        string='Plan To Date', store=False,
    )

    min_line_date = fields.Date(
        string='Earliest Allowed Date',
        compute='_compute_min_line_date', store=False,
    )

    planned_qty = fields.Float(
        string='Planned Qty', readonly=True, copy=False,
        help='Snapshot of Quantity taken when the plan was activated. '
             'It never changes afterwards, so the report can compare '
             'planned vs. current quantity.',
    )

    product_id  = fields.Many2one('product.product', string="Product")
    quantity    = fields.Float(string="Quantity", required=True, default=0.0)
    on_hand_qty = fields.Float(string='On Hand Quantity', compute='_compute_on_hand_qty')

    purchase_requisition_id = fields.Many2one(
        'purchase.requisition',
        string='Latest Purchase Requisition',
        readonly=True, copy=False,
        help='Most recent Purchase Requisition generated from this line. '
             'Kept for convenience; the full history is in Purchase Requisitions.',
    )

    purchase_requisition_ids = fields.Many2many(
        'purchase.requisition',
        string='Purchase Requisitions',
        readonly=True, copy=False,
        help='Every Purchase Requisition ever generated from this line. '
             'Difference mode subtracts the sum of all of them.',
    )

    location_id = fields.Many2one(
        'stock.location', string='Location',
        domain="[('usage', 'in', ['internal'])]",
        help='Destination location for this line. Auto-filled from the '
             'plan\'s Destination Location when the plan is activated.',
    )

    transfer_picking_id = fields.Many2one(
        'stock.picking',
        string='Internal Transfer',
        readonly=True, copy=False,
        help='Internal transfer that delivered this planning line to its '
             'destination location.',
    )
    transferred = fields.Boolean(
        string='Transferred',
        compute='_compute_transferred', store=True,
    )

    @api.depends('transfer_picking_id')
    def _compute_transferred(self):
        for rec in self:
            rec.transferred = bool(rec.transfer_picking_id)

    @api.depends('monthly_planning_id', 'monthly_planning_id.from_date')
    def _compute_min_line_date(self):
        today = fields.Date.today()
        for rec in self:
            plan_from = rec.monthly_planning_id.from_date
            rec.min_line_date = plan_from if (plan_from and plan_from > today) else today

    @api.model
    def _default_line_date(self):
        today = fields.Date.today()
        parent_id = self.env.context.get('default_monthly_planning_id')
        if parent_id:
            parent = self.env['monthly.planning'].browse(parent_id)
            if parent.from_date and parent.from_date > today:
                return parent.from_date
        return today

    @api.constrains('date', 'monthly_planning_id')
    def _check_line_no_backdate(self):
        today = fields.Date.today()
        for rec in self:
            if not rec.date:
                continue
            if rec._origin.id is None and rec.date < today:
                raise ValidationError(
                    "Line Date cannot be in the past. Earliest allowed: %s." % today
                )
            plan = rec.monthly_planning_id
            if plan and plan.from_date and plan.to_date:
                if not (plan.from_date <= rec.date <= plan.to_date):
                    raise ValidationError(
                        "Line Date %s is outside the planning period %s → %s."
                        % (rec.date, plan.from_date, plan.to_date)
                    )

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

    def write(self, vals):
        for rec in self:
            if rec.monthly_planning_id.is_locked:
                raise ValidationError(
                    "This Monthly Planning is locked (period ended on %s). "
                    "Lines cannot be modified."
                    % rec.monthly_planning_id.to_date
                )
            if rec.monthly_planning_id.state == 'active' and 'product_id' in vals:
                raise ValidationError(
                    "This Monthly Planning is Active. "
                    "You cannot change the product on an active plan."
                )
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            plan_id = vals.get('monthly_planning_id')
            if plan_id:
                plan = self.env['monthly.planning'].browse(plan_id)
                if plan.state == 'active':
                    raise ValidationError(
                        "You cannot add new lines to an Active plan. "
                        "Set it back to Draft first."
                    )
        return super().create(vals_list)

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