# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError
from odoo.osv import expression


class PosDdReport(models.Model):
    _name = 'pos.dd.report'
    _description = 'POS Orders & Direct Deposits Reporting'
    _auto = False
    _rec_name = 'reference'
    _order = 'date desc, id desc'

    # ---- shared columns ----
    date = fields.Datetime('Date', readonly=True)
    reference = fields.Char('Reference', readonly=True)
    source_model = fields.Selection([
        ('pos.order', 'POS Order'),
        ('direct.deposit', 'Direct Deposit'),
    ], string='Source', readonly=True)
    source_id = fields.Integer('Source ID', readonly=True)
    partner_id = fields.Many2one('res.partner', 'Customer / Donor', readonly=True)
    partner_phone = fields.Char('Contact Number', readonly=True)
    user_id = fields.Many2one('res.users', 'Cashier / User', readonly=True)
    currency_id = fields.Many2one('res.currency', 'Currency', readonly=True)
    amount = fields.Monetary('Amount', currency_field='currency_id', readonly=True)
    amount_paid = fields.Monetary('Paid', currency_field='currency_id', readonly=True)
    is_refund = fields.Boolean('Refund', readonly=True)
    state = fields.Char('State', readonly=True)

    # ---- POS-specific ----
    config_id = fields.Many2one('pos.config', 'Point of Sale', readonly=True)
    session_id = fields.Many2one('pos.session', 'Session', readonly=True)
    payment_methods = fields.Char('Payment Methods', readonly=True)

    # ---- DD-specific ----
    bank_id = fields.Many2one('account.journal', 'Bank', readonly=True)
    payment_type = fields.Char('Payment Type', readonly=True)
    transaction_ref = fields.Char('Transaction Ref', readonly=True)
    remarks = fields.Text('Remarks', readonly=True)

    # ---- Analytics & Product ----
    analytic_account_id = fields.Many2one('account.analytic.account', 'Branch', readonly=True)
    zone_id = fields.Many2one('account.analytic.account', 'Zone', readonly=True)
    city_id = fields.Many2one('account.analytic.account', 'City', readonly=True)
    province_id = fields.Many2one('account.analytic.account', 'Province', readonly=True)
    product_id = fields.Many2one('product.product', 'Product', readonly=True)
    category_id = fields.Many2one('product.category', 'Product Category', readonly=True)

    # ---- Date-range search helper (not a view column) ----
    date_day = fields.Date(
        'Day', compute='_compute_date_day', search='_search_date_day',
        help="Transaction date in the user's timezone. Backs the "
             "'Date From' / 'Date To' search fields so whole days are matched.")

    @api.depends('date')
    def _compute_date_day(self):
        for rec in self:
            rec.date_day = fields.Date.context_today(rec, rec.date) if rec.date else False

    def _search_date_day(self, operator, value):
        """Translate a local calendar day into UTC bounds on ``date``."""
        if not value:
            return [('date', operator, value)]
        if operator not in ('=', '!=', '<', '<=', '>', '>='):
            raise UserError(_("Operator '%s' is not supported on Day.", operator))

        tz = pytz.timezone(self.env.context.get('tz') or self.env.user.tz or 'UTC')
        day = fields.Date.to_date(value)

        def utc_midnight(d):
            local = tz.localize(datetime.combine(d, time.min))
            return local.astimezone(pytz.utc).replace(tzinfo=None)

        start = utc_midnight(day)
        end = utc_midnight(day + timedelta(days=1))
        return {
            '>=': [('date', '>=', start)],
            '>': [('date', '>=', end)],
            '<': [('date', '<', start)],
            '<=': [('date', '<', end)],
            '=': ['&', ('date', '>=', start), ('date', '<', end)],
            '!=': ['|', ('date', '<', start), ('date', '>=', end)],
        }[operator]

    # ------------------------------------------------------------------
    def init(self):
        tools.drop_view_if_exists(self._cr, 'pos_dd_report')

        self._cr.execute("""
            CREATE OR REPLACE VIEW pos_dd_report AS
            WITH RECURSIVE loc_tree AS (
                SELECT id, parent_id, 1 AS level,
                       id AS province_id, NULL::int AS city_id, NULL::int AS zone_id
                FROM account_analytic_account
                WHERE parent_id IS NULL
                UNION ALL
                SELECT a.id, a.parent_id, lt.level + 1,
                    lt.province_id,
                    CASE WHEN lt.level + 1 = 2 THEN a.id ELSE lt.city_id END,
                    CASE WHEN lt.level + 1 = 3 THEN a.id ELSE lt.zone_id END
                FROM account_analytic_account a
                JOIN loc_tree lt ON a.parent_id = lt.id
                WHERE lt.level < 10
            )
            SELECT
                (pol.id * 2)::integer AS id,
                po.id AS source_id,
                'pos.order'::varchar AS source_model,
                po.name AS reference,
                po.date_order AS date,
                po.partner_id,
                COALESCE(NULLIF(rp.phone, ''), NULLIF(rp.mobile, ''), '')::varchar AS partner_phone,
                po.user_id,
                rc.currency_id,
                pol.price_subtotal_incl AS amount,
                CASE
                    WHEN po.amount_total = 0 THEN 0
                    ELSE po.amount_paid * (pol.price_subtotal_incl / po.amount_total)
                END AS amount_paid,
                (pol.price_subtotal_incl < 0) AS is_refund,
                po.state,
                po.config_id,
                po.session_id,
                (
                    SELECT string_agg(DISTINCT ppm.name->>'en_US', ', ')
                    FROM pos_payment pp
                    JOIN pos_payment_method ppm ON ppm.id = pp.payment_method_id
                    WHERE pp.pos_order_id = po.id
                ) AS payment_methods,
                NULL::integer AS bank_id,
                NULL::varchar AS payment_type,
                NULL::varchar AS transaction_ref,
                NULL::text AS remarks,
                COALESCE(pc.analytic_account_id, ps.analytic_account_id, emp.analytic_account_id) AS analytic_account_id,
                lt.zone_id AS zone_id,
                lt.city_id AS city_id,
                lt.province_id AS province_id,
                pol.product_id AS product_id,
                pt.categ_id AS category_id
            FROM pos_order_line pol
            INNER JOIN pos_order po ON po.id = pol.order_id
            LEFT JOIN pos_config pc ON pc.id = po.config_id
            LEFT JOIN pos_session ps ON ps.id = po.session_id
            -- one employee per cashier (a user can have one per company): a plain
            -- join would repeat the order line and double its amount
            LEFT JOIN LATERAL (
                SELECT e.analytic_account_id FROM hr_employee e
                 WHERE e.user_id = po.user_id AND e.active
                 ORDER BY (e.company_id = po.company_id) DESC, e.id LIMIT 1
            ) emp ON TRUE
            LEFT JOIN res_company rc ON rc.id = po.company_id
            LEFT JOIN res_partner rp ON rp.id = po.partner_id
            LEFT JOIN product_product pp ON pp.id = pol.product_id
            LEFT JOIN product_template pt ON pt.id = pp.product_tmpl_id
            LEFT JOIN loc_tree lt ON lt.id = COALESCE(pc.analytic_account_id, ps.analytic_account_id, emp.analytic_account_id)

            UNION ALL

            SELECT
                (ddl.id * 2 + 1)::integer AS id,
                dd.id AS source_id,
                'direct.deposit'::varchar AS source_model,
                dd.name AS reference,
                dd.create_date AS date,
                dd.donor_id AS partner_id,
                COALESCE(NULLIF(rp.phone, ''), NULLIF(rp.mobile, ''), '')::varchar AS partner_phone,
                dd.user_id AS user_id,
                dd.currency_id AS currency_id,
                (COALESCE(ddl.amount, 0) * COALESCE(ddl.quantity, 1))::numeric AS amount,
                CASE
                    WHEN dd.state IN ('clear', 'transferred')
                        THEN (COALESCE(ddl.amount, 0) * COALESCE(ddl.quantity, 1))::numeric
                    ELSE 0
                END AS amount_paid,
                FALSE AS is_refund,
                dd.state AS state,
                NULL::integer AS config_id,
                NULL::integer AS session_id,
                NULL::text AS payment_methods,
                dd.bank_id AS bank_id,
                dd.payment_type AS payment_type,
                dd.transaction_ref AS transaction_ref,
                ddl.remarks AS remarks,
                dd.analytic_account_id AS analytic_account_id,
                lt.zone_id AS zone_id,
                lt.city_id AS city_id,
                lt.province_id AS province_id,
                ddl.product_id::integer AS product_id,
                pt.categ_id::integer AS category_id
            FROM direct_deposit_line ddl
            INNER JOIN direct_deposit dd ON dd.id = ddl.direct_deposit_id
            LEFT JOIN res_partner rp ON rp.id = dd.donor_id
            LEFT JOIN product_product pp ON pp.id = ddl.product_id
            LEFT JOIN product_template pt ON pt.id = pp.product_tmpl_id
            LEFT JOIN loc_tree lt ON lt.id = dd.analytic_account_id
        """)

    # ------------------------------------------------------------------
    # ACCESS HELPERS
    # ------------------------------------------------------------------
    @api.model
    def get_location_filter_options(self):
        """Cities and branches (Location plan) the current user may report on."""
        self.check_access_rights('read')
        Account = self.env['account.analytic.account'].sudo()
        location = [('plan_id.name', '=', 'Location')]
        city_domain = location + [('parent_id', '!=', False), ('parent_id.parent_id', '=', False)]
        branch_domain = location + [('parent_id.parent_id.parent_id', '!=', False)]

        allowed = self.env.user.pos_dd_report_analytic_ids
        if allowed:
            # cities above or inside the user's allowed locations; branches inside them
            city_domain += ['|', ('id', 'parent_of', allowed.ids), ('id', 'child_of', allowed.ids)]
            branch_domain += [('id', 'child_of', allowed.ids)]

        cities = Account.search(city_domain, order='name')
        branches = Account.search(branch_domain, order='name')
        return {
            'cities': [{'id': c.id, 'name': c.name} for c in cities],
            'branches': [{
                'id': b.id,
                'name': b.name,
                'city_id': b.parent_id.parent_id.id or False,
                'city_name': b.parent_id.parent_id.name or '',
            } for b in branches],
        }

    @api.model
    def _get_user_category_domain(self):
        """
        Category-restriction domain for the *current* user.
        Returns [] when the user has no category restriction (full access).
        """
        allowed = self.env.user.pos_dd_report_category_ids
        if not allowed:
            return []
        return [('category_id', 'child_of', allowed.ids)]

    @api.model
    def _get_user_location_domain(self):
        """Location-restriction domain for the current user ([] = unrestricted)."""
        allowed = self.env.user.pos_dd_report_analytic_ids
        if not allowed:
            return []
        return [('analytic_account_id', 'child_of', allowed.ids)]

    @api.model
    def _get_user_access_domain(self):
        """Combined category + location restriction domain."""
        return expression.AND([
            self._get_user_location_domain(),
            self._get_user_category_domain(),
        ])

    # ------------------------------------------------------------------
    def action_open_source(self):
        """Open the underlying POS order or Direct Deposit form."""
        self.ensure_one()
        if self.source_model == 'pos.order':
            return {
                'name': 'POS Order',
                'type': 'ir.actions.act_window',
                'res_model': 'pos.order',
                'res_id': self.source_id,
                'view_mode': 'form',
                'target': 'current',
            }
        elif self.source_model == 'direct.deposit':
            return {
                'name': 'Direct Deposit',
                'type': 'ir.actions.act_window',
                'res_model': 'direct.deposit',
                'res_id': self.source_id,
                'view_mode': 'form',
                'target': 'current',
            }
        return False