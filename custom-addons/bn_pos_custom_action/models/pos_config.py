from odoo import fields, models
from odoo.tools.sql import column_exists


class PosConfig(models.Model):
    _inherit = 'pos.config'

    counter = fields.Integer(string="Counter", default=1)
    sequence = fields.Integer(string="Sequence", default=1)

    user_ids = fields.Many2many('res.users', string="Users")

    # The Branch of the shop: its sessions, orders and every record made or
    # paid at it are tagged with it (not with the cashier's branch).
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string="Branch", tracking=True, index='btree_not_null',
        domain="[('location_option_id.name', '=', 'Branch')]",
        help="Analytic account (Branch) of this shop: its sessions, orders, receipts (DN #) "
             "and the POS records made at it carry this branch.")
    branch_code = fields.Char(related='analytic_account_id.code', string="Branch Code")
    branch_name = fields.Char(related='analytic_account_id.name', string="Branch Name")

    def init(self):
        """A shop without a Branch gets the one its latest session had
        (the cashier's branch until now)."""
        super().init()
        if not column_exists(self.env.cr, 'pos_session', 'analytic_account_id'):
            return
        self.env.cr.execute("""
            UPDATE pos_config c SET analytic_account_id = s.analytic_account_id
              FROM (SELECT DISTINCT ON (config_id) config_id, analytic_account_id
                      FROM pos_session WHERE analytic_account_id IS NOT NULL
                     ORDER BY config_id, id DESC) s
             WHERE s.config_id = c.id AND c.analytic_account_id IS NULL
        """)
