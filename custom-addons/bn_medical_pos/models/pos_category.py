from odoo import api, fields, models

# Product fields that change what the Medical & Health counters show
WATCHED_PRODUCT_FIELDS = {'pos_categ_ids', 'available_in_pos', 'sale_ok', 'active'}


class PosCategory(models.Model):
    _inherit = 'pos.category'

    mh_medical = fields.Boolean(
        string="Medical & Health",
        help="The products of this category (and of its sub-categories) are shown at the Medical & Health counters.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        categories = super().create(vals_list)
        if any(categories.mapped('mh_medical')):
            self._mh_notify_counters()
        return categories

    def write(self, vals):
        notify = 'mh_medical' in vals or (
            {'name', 'parent_id', 'sequence', 'image_128'} & set(vals) and any(self.mapped('mh_medical')))
        res = super().write(vals)
        if notify:
            self._mh_notify_counters()
        return res

    def unlink(self):
        notify = any(self.mapped('mh_medical'))
        res = super().unlink()
        if notify:
            self.env['pos.category']._mh_notify_counters()
        return res

    @api.model
    def _mh_notify_counters(self):
        """Tell the open Medical & Health counters to refresh their categories and products"""
        sessions = self.env['pos.session'].sudo().search([
            ('config_id.is_medical_pos', '=', True),
            ('state', 'in', ('opening_control', 'opened')),
        ])
        for session in sessions:
            self.env['bus.bus']._sendone(session._get_bus_channel_name(), 'MH_CATALOG_CHANGED', {})


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.model_create_multi
    def create(self, vals_list):
        templates = super().create(vals_list)
        if any(templates.pos_categ_ids.mapped('mh_medical')):
            self.env['pos.category']._mh_notify_counters()
        return templates

    def write(self, vals):
        watched = WATCHED_PRODUCT_FIELDS & set(vals)
        was_medical = watched and any(self.pos_categ_ids.mapped('mh_medical'))
        res = super().write(vals)
        if watched and (was_medical or any(self.pos_categ_ids.mapped('mh_medical'))):
            self.env['pos.category']._mh_notify_counters()
        return res
