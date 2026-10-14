from odoo import api, models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _visible_menu_ids(self, debug=False):
        visible = super()._visible_menu_ids(debug)
        user = self.env.user
        if user.has_group('bn_inventory_customization.group_stock_user_reporting') \
                and not user.has_group('stock.group_stock_manager'):
            # "User + Reporting" does not get Inventory > Products and its submenus
            products_menu = self.env.ref('stock.menu_stock_inventory_control', raise_if_not_found=False)
            if products_menu:
                hidden = self.with_context(**{'ir.ui.menu.full_list': True}).search(
                    [('id', 'child_of', products_menu.id)])
                # super() returns the cached set, build a new one
                visible = visible - set(hidden.ids)
        return visible
