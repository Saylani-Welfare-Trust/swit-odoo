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

    # ---- access control ----
    analytic_account_id = fields.Many2one(
        'account.analytic.account', 'Branch', readonly=True)

    # ------------------------------------------------------------------
    def init(self):
        tools.drop_view_if_exists(self._cr, 'pos_dd_report')
        self._cr.execute("""
            CREATE OR REPLACE VIEW pos_dd_report AS (
                SELECT
                    (po.id * 2)::integer                                  AS id,
                    po.id                                                 AS source_id,
                    'pos.order'::varchar                                  AS source_model,
                    po.name                                               AS reference,
                    po.date_order                                         AS date,
                    po.partner_id                                         AS partner_id,
                    po.user_id                                            AS user_id,
                    po.currency_id                                        AS currency_id,
                    po.amount_total                                       AS amount,
                    po.amount_paid                                        AS amount_paid,
                    (po.amount_total < 0)                                 AS is_refund,
                    po.state                                              AS state,
                    po.config_id                                          AS config_id,
                    po.session_id                                         AS session_id,
                    (
                        SELECT string_agg(DISTINCT ppm.name->>'en_US', ', ')
                        FROM pos_payment pp
                        JOIN pos_payment_method ppm
                            ON ppm.id = pp.payment_method_id
                        WHERE pp.pos_order_id = po.id
                    )                                                     AS payment_methods,
                    NULL::integer                                         AS bank_id,
                    NULL::varchar                                         AS payment_type,
                    NULL::varchar                                         AS transaction_ref,
                    NULL::text                                            AS remarks,
                    aa.id                                                 AS analytic_account_id
                FROM pos_order po
                LEFT JOIN pos_config pc
                       ON pc.id = po.config_id
                LEFT JOIN account_analytic_account aa
                       ON aa.id = pc.analytic_account_id

                UNION ALL

                SELECT
                    (dd.id * 2 + 1)::integer                              AS id,
                    dd.id                                                 AS source_id,
                    'direct.deposit'::varchar                             AS source_model,
                    dd.name                                               AS reference,
                    dd.create_date                                        AS date,
                    dd.donor_id                                           AS partner_id,
                    dd.user_id                                            AS user_id,
                    dd.currency_id                                        AS currency_id,
                    dd.amount                                             AS amount,
                    dd.amount                                             AS amount_paid,
                    FALSE                                                 AS is_refund,
                    dd.state                                              AS state,
                    NULL::integer                                         AS config_id,
                    NULL::integer                                         AS session_id,
                    NULL::varchar                                         AS payment_methods,
                    dd.bank_id                                            AS bank_id,
                    dd.payment_type                                       AS payment_type,
                    dd.transaction_ref                                    AS transaction_ref,
                    dd.remarks                                            AS remarks,
                    dd.analytic_account_id                                AS analytic_account_id
                FROM direct_deposit dd
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