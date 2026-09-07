from odoo import models, fields, api
from odoo.exceptions import ValidationError
import calendar
from datetime import datetime

type_selection = [
    ('ration', 'Ration'),
    ('distribution', 'Distribution'),
]

state_selection = [
    ('draft', 'Draft'),
    ('issued', 'Issued'),
]

SOURCE_TAB_SELECTION = [
    ('kitchen', 'Kitchen'),
    ('madaris', 'Madaris'),
    ('medical', 'Medical'),
    ('livestock', 'Livestock'),
    ('food', 'Food'),
    ('ration', 'Ration'),
    ('meat', 'Meat'),
]

# We need the month mapping for computations (same as in monthly.planning)
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


class DailyPlanning(models.Model):
    _name = 'daily.planning'
    _description = 'Daily Planning'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = 'name'
    _order = 'name desc'

    name = fields.Char(string='Reference', readonly=True, copy=False)
    monthly_planning_id = fields.Many2one('monthly.planning', string='Monthly Planning', required=True)
    source_tab = fields.Selection(
        selection=SOURCE_TAB_SELECTION,
        string='Source Tab',
        required=True,
        # default='all'
    )
    day = fields.Integer(string='Day', required=True, default=1)
    date = fields.Date(string='Date', compute='_compute_date', store=True)

    type = fields.Selection(selection=type_selection, string='Type')
    state = fields.Selection(selection=state_selection, string='State', default='draft')

    picking_id = fields.Many2one('stock.picking', string='Picking')
    daily_planning_line_ids = fields.One2many('daily.planning.line', 'daily_planning_id', string='Daily Planning Lines')

    # ─── Compute full date from month/year of monthly planning + day ───
    @api.depends('monthly_planning_id', 'day')
    def _compute_date(self):
        for rec in self:
            if rec.monthly_planning_id and rec.day:
                month_str = rec.monthly_planning_id.month
                month_num = dict(MONTH_SELECTION)[month_str]  
                # Convert month_str to number
                month_num = [m[0] for m in MONTH_SELECTION].index(month_str) + 1
                year = rec.monthly_planning_id.year
                days_in_month = calendar.monthrange(year, month_num)[1]
                if 1 <= rec.day <= days_in_month:
                    rec.date = datetime(year, month_num, rec.day).date()
                else:
                    rec.date = False
            else:
                rec.date = False

    # ─── Validate day against days in month ──────────────────────────
    @api.constrains('day', 'monthly_planning_id')
    def _check_day(self):
        for rec in self:
            if rec.monthly_planning_id and rec.day:
                month_str = rec.monthly_planning_id.month
                month_num = [m[0] for m in MONTH_SELECTION].index(month_str) + 1
                year = rec.monthly_planning_id.year
                days_in_month = calendar.monthrange(year, month_num)[1]
                if not (1 <= rec.day <= days_in_month):
                    raise ValidationError(f"Day must be between 1 and {days_in_month} for the selected month.")

    # ─── Auto‑populate lines when tab, monthly, or day changes ──────
    @api.onchange('monthly_planning_id', 'source_tab', 'day')
    def _onchange_monthly_planning_tab_day(self):
        if not self.monthly_planning_id or not self.source_tab or not self.day:
            self.daily_planning_line_ids = [(5, 0, 0)]
            return

        month_str = self.monthly_planning_id.month
        month_num = [m[0] for m in MONTH_SELECTION].index(month_str) + 1
        year = self.monthly_planning_id.year
        try:
            date_obj = datetime(year, month_num, self.day).date()
        except ValueError:
            return

        self.daily_planning_line_ids = [(5, 0, 0)]

        tab_map = {
            'kitchen': 'kitchen_line_ids',
            'madaris': 'madaris_line_ids',
            'medical': 'medical_line_ids',
            'livestock': 'livestock_line_ids',
            'food': 'food_line_ids',
            'ration': 'ration_line_ids',
            'meat': 'meat_line_ids',
        }

        field_name = tab_map.get(self.source_tab)
        if not field_name:
            return

        mp = self.monthly_planning_id
        lines = getattr(mp, field_name).filtered(lambda l: l.date == date_obj and l.product_id)

        commands = []
        for line in lines:
            commands.append((0, 0, {
                'product_id': line.product_id.id,
                'quantity': line.quantity,
                'monthly_line_ref': f"{line._name},{line.id}",
            }))

        if commands:
            self.daily_planning_line_ids = commands

    def action_send_issuance(self):
        StockPicking = self.env['stock.picking']

        # ✅ Source = Main Stock
        source_loc = self.env.ref('stock.stock_location_stock')

        # ✅ Destination = Distribution (your custom location)
        dest_loc = self.env['stock.location'].search([
            ('name', 'ilike', 'Distribution'),
            ('usage', '=', 'internal'),
        ], limit=1)

        if not dest_loc:
            raise ValidationError(
                "Distribution location not found. Please create it in Inventory."
            )

        picking_type = self.env.ref('stock.picking_type_internal')

        for rec in self:
            picking = StockPicking.create({
                'picking_type_id': picking_type.id,
                'location_id': source_loc.id,
                'location_dest_id': dest_loc.id,
                'scheduled_date': rec.date,
            })

            move_vals = []
            for line in rec.daily_planning_line_ids:
                product = line.product_id

                if not product:
                    continue

                move_vals.append((0, 0, {
                    'name': product.display_name,
                    'product_id': product.id,
                    'product_uom_qty': 1.0,
                    'product_uom': product.uom_id.id,
                    'location_id': source_loc.id,
                    'location_dest_id': dest_loc.id,
                }))

            if not move_vals:
                picking.unlink()
                raise ValidationError(
                    f"No products found on Daily Planning {rec.id}"
                )

            picking.write({'move_ids_without_package': move_vals})
            picking.action_confirm()
            picking.action_assign()

            if picking.state == 'assigned':
                picking.button_validate()

            rec.picking_id = picking.id

        self.state = 'issued';

        return True
    
    @api.model
    def create(self, vals):
        if not vals.get('name'):
            vals['name'] = self.env['ir.sequence'].next_by_code('daily.planning') or '/'
        return super(DailyPlanning, self).create(vals)
