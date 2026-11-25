from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    @api.model
    def _search(self, domain, *args, **kwargs):
        """Branch pickers: with ``branch_scope`` in the context (set on the field
        in the view), offer only the user's analytic accounts in scope
        (res.users.scope_analytic_account_ids). Only a convenience: the record
        rules are what restrict the records. Administrators and "Unrestricted
        Access" see every account."""
        if self.env.context.get('branch_scope') and not self.env.su:
            user = self.env.user
            if not (user.has_group('base.group_system')
                    or user.has_group('bn_stock_location.stock_scope_unrestricted_group')):
                domain = expression.AND([domain or [], [('id', 'in', user.scope_analytic_account_ids.ids)]])
        return super()._search(domain, *args, **kwargs)


class AccountAnalyticAccountNode(models.Model):
    """A Branch / Site of the Location tree (Province > City > Zone > Branch / Site)
    and the warehouses it runs."""
    _inherit = 'account.analytic.account'

    warehouse_ids = fields.One2many('stock.warehouse', 'node_id', string='Warehouses')
    default_warehouse_id = fields.Many2one(
        'stock.warehouse', string='Default Warehouse', domain="[('node_id', '=', id)]",
        help="The warehouse the programs use for a document of this Branch / Site that has no "
             "location of its own. Not needed when the Branch / Site has a single warehouse.")

    @api.constrains('default_warehouse_id')
    def _check_default_warehouse(self):
        for node in self:
            if node.default_warehouse_id and node.default_warehouse_id.node_id != node:
                raise ValidationError(_("The default warehouse of %(node)s must be one of its own warehouses "
                                        "(%(warehouse)s belongs to %(other)s).",
                                        node=node.display_name, warehouse=node.default_warehouse_id.display_name,
                                        other=node.default_warehouse_id.node_id.display_name or _('no Branch / Site')))

    def _node_warehouse(self, raise_if_none=True):
        """The warehouse of this Branch / Site for a document without a location:
        its Default Warehouse, else its only warehouse; several warehouses and no
        default: refused (never guessed)."""
        self.ensure_one()
        node = self.sudo()
        if node.default_warehouse_id:
            return node.default_warehouse_id.sudo(False)
        warehouses = node.warehouse_ids
        if len(warehouses) == 1:
            return warehouses.sudo(False)
        if raise_if_none and len(warehouses) > 1:
            raise UserError(_("%s has several warehouses: set its Default Warehouse "
                              "(Accounting > Analytic Accounts).", node.display_name))
        return self.env['stock.warehouse']
