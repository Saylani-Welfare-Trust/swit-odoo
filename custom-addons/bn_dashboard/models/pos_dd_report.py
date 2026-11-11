# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools

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

    # ---- Analytics & Product (New filters) ----
    analytic_account_id = fields.Many2one('account.analytic.account', 'Branch', readonly=True)
    zone_id = fields.Many2one('account.analytic.account', 'Zone', readonly=True)
    city_id = fields.Many2one('account.analytic.account', 'City', readonly=True)
    province_id = fields.Many2one('account.analytic.account', 'Province', readonly=True)
    product_id = fields.Many2one('product.product', 'Product', readonly=True)
    category_id = fields.Many2one('product.category', 'Product Category', readonly=True)

    # ------------------------------------------------------------------
    def init(self):
        tools.drop_view_if_exists(self._cr, 'pos_dd_report')

        # ─────────────────────────────────────────────────────────────
        # 1. Auto-detect the direct.deposit line model
        # ─────────────────────────────────────────────────────────────
        DD = self.env['direct.deposit']
        dd_line_model = None
        dd_fk_field   = None
        dd_prod_field = None
        dd_amt_field  = None

        # Prefer these common names when multiple one2many fields exist
        preferred = ['line_ids', 'lines', 'deposit_line_ids',
                     'order_line', 'product_line_ids']

        candidates = [f for f in preferred if f in DD._fields] + \
                     [f for f in DD._fields if f not in preferred]

        for fname in candidates:
            f = DD._fields[fname]
            if f.type != 'one2many':
                continue
            LineModel = self.env[f.comodel_name]
            if 'product_id' not in LineModel._fields:
                continue

            dd_line_model = LineModel
            # Find the FK back to direct.deposit
            for ln, lf in LineModel._fields.items():
                if lf.type == 'many2one' and lf.comodel_name == 'direct.deposit':
                    dd_fk_field = ln
                    break

            dd_prod_field = 'product_id'
            # Find the amount field
            for cand in ('amount', 'price_subtotal', 'price_total',
                         'subtotal', 'line_amount'):
                if cand in LineModel._fields:
                    dd_amt_field = cand
                    break
            # Fallback: use price_unit * qty
            if not dd_amt_field and 'price_unit' in LineModel._fields:
                for qty in ('quantity', 'qty', 'product_uom_qty'):
                    if qty in LineModel._fields:
                        dd_amt_field = f"({dd_prod_field and 'price_unit'} * {qty})"
                        dd_amt_field = None  # handled below
                        break

            _logger = __import__('logging').getLogger(__name__)
            _logger.info(
                "pos.dd.report: detected DD line model=%s | fk=%s | product=%s | amount=%s",
                dd_line_model._name, dd_fk_field, dd_prod_field, dd_amt_field,
            )
            break

        # ─────────────────────────────────────────────────────────────
        # 2. Build the Direct Deposit SELECT fragment
        # ─────────────────────────────────────────────────────────────
        if dd_line_model and dd_fk_field and dd_amt_field:
            dd_table = dd_line_model._table
            dd_select = f"""
                SELECT
                    (ddl.id * 2 + 1)::integer AS id,
                    dd.id AS source_id,
                    'direct.deposit'::varchar AS source_model,
                    dd.name AS reference,
                    dd.create_date AS date,
                    dd.donor_id AS partner_id,
                    dd.user_id AS user_id,
                    dd.currency_id AS currency_id,
                    COALESCE(ddl.{dd_amt_field}, 0)::numeric AS amount,
                    COALESCE(ddl.{dd_amt_field}, 0)::numeric AS amount_paid,
                    FALSE AS is_refund,
                    dd.state AS state,
                    NULL::integer AS config_id,
                    NULL::integer AS session_id,
                    NULL::text AS payment_methods,
                    dd.bank_id AS bank_id,
                    dd.payment_type AS payment_type,
                    dd.transaction_ref AS transaction_ref,
                    dd.remarks AS remarks,
                    dd.analytic_account_id AS analytic_account_id,
                    zone.id AS zone_id,
                    city.id AS city_id,
                    province.id AS province_id,
                    ddl.{dd_prod_field}::integer AS product_id,
                    pt.categ_id::integer AS category_id
                FROM {dd_table} ddl
                INNER JOIN direct_deposit dd ON dd.id = ddl.{dd_fk_field}
                LEFT JOIN product_product pp ON pp.id = ddl.{dd_prod_field}
                LEFT JOIN product_template pt ON pt.id = pp.product_tmpl_id
                LEFT JOIN account_analytic_account aa ON aa.id = dd.analytic_account_id
                LEFT JOIN account_analytic_account zone ON zone.id = aa.parent_id
                LEFT JOIN account_analytic_account city ON city.id = zone.parent_id
                LEFT JOIN account_analytic_account province ON province.id = city.parent_id
            """
        else:
            # Fallback: header-only (will still show "None" for product)
            dd_select = """
                SELECT
                    (dd.id * 2 + 1)::integer AS id,
                    dd.id AS source_id,
                    'direct.deposit'::varchar AS source_model,
                    dd.name AS reference,
                    dd.create_date AS date,
                    dd.donor_id AS partner_id,
                    dd.user_id AS user_id,
                    dd.currency_id AS currency_id,
                    dd.amount AS amount,
                    dd.amount AS amount_paid,
                    FALSE AS is_refund,
                    dd.state AS state,
                    NULL::integer AS config_id,
                    NULL::integer AS session_id,
                    NULL::text AS payment_methods,
                    dd.bank_id AS bank_id,
                    dd.payment_type AS payment_type,
                    dd.transaction_ref AS transaction_ref,
                    dd.remarks AS remarks,
                    dd.analytic_account_id AS analytic_account_id,
                    zone.id AS zone_id,
                    city.id AS city_id,
                    province.id AS province_id,
                    NULL::integer AS product_id,
                    NULL::integer AS category_id
                FROM direct_deposit dd
                LEFT JOIN account_analytic_account aa ON aa.id = dd.analytic_account_id
                LEFT JOIN account_analytic_account zone ON zone.id = aa.parent_id
                LEFT JOIN account_analytic_account city ON city.id = zone.parent_id
                LEFT JOIN account_analytic_account province ON province.id = city.parent_id
            """

        # ─────────────────────────────────────────────────────────────
        # 3. Build the full view
        # ─────────────────────────────────────────────────────────────
        self._cr.execute(f"""
            CREATE OR REPLACE VIEW pos_dd_report AS (
                -- POS order lines
                SELECT
                    (pol.id * 2)::integer AS id,
                    po.id AS source_id,
                    'pos.order'::varchar AS source_model,
                    po.name AS reference,
                    po.date_order AS date,
                    po.partner_id,
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
                    aa.id AS analytic_account_id,
                    zone.id AS zone_id,
                    city.id AS city_id,
                    province.id AS province_id,
                    pol.product_id AS product_id,
                    pt.categ_id AS category_id
                FROM pos_order_line pol
                INNER JOIN pos_order po ON po.id = pol.order_id
                LEFT JOIN pos_config pc ON pc.id = po.config_id
                LEFT JOIN res_company rc ON rc.id = po.company_id
                LEFT JOIN account_analytic_account aa ON aa.id = pc.analytic_account_id
                LEFT JOIN account_analytic_account zone ON zone.id = aa.parent_id
                LEFT JOIN account_analytic_account city ON city.id = zone.parent_id
                LEFT JOIN account_analytic_account province ON province.id = city.parent_id
                LEFT JOIN product_product pp ON pp.id = pol.product_id
                LEFT JOIN product_template pt ON pt.id = pp.product_tmpl_id

                UNION ALL

                -- Direct deposit lines (with product + category)
                {dd_select}
            )
        """)

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