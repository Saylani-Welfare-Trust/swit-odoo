# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResPartnerCategory(models.Model):
    """Record Search programmes, the part of main's profile tags that Welfare
    and Sadqa e Jariya use: a tag with a Record Search code is a programme a
    module's Record Search registers for (its menu passes the code, e.g.
    default_program_code = 'sadqa_e_jariya'), and the module's menus follow
    the programme (shown while it is enabled)."""
    _inherit = 'res.partner.category'

    registration_program_code = fields.Char(
        'Record Search Code', copy=False,
        help="Makes this tag a programme offered by Record Search. Each module's Record Search "
             "menu passes this code (e.g. sadqa_e_jariya). Leave empty for other tags.")
    registration_program_active = fields.Boolean(
        'Programme Enabled', default=True,
        help="Off: the programme's menus in its module are hidden and Record Search no longer "
             "offers it. On again: they come back.")
    program_menu_ids = fields.Many2many(
        'ir.ui.menu', 'res_partner_category_program_menu_rel', 'category_id', 'menu_id',
        string='Programme Menus', readonly=True, copy=False,
        help="Menus of the module of this programme, linked on install / upgrade. Shown while the "
             "programme is enabled, hidden when it is not.")
    registration_role = fields.Selection([('donee', 'Donee'), ('donor', 'Donor')], string='Registers as',
                                         default='donee')
    registration_kind = fields.Selection([
        ('choose', 'Chosen at the search'),
        ('individual', 'Individual'),
        ('institution', 'Corporate / Institute'),
    ], string='Contact Kind', default='choose',
        help="Individual / Corporate-Institute tag given with the programme.")
    registration_required_field_ids = fields.Many2many(
        'ir.model.fields', 'res_partner_category_required_field_rel', 'category_id', 'field_id',
        string='Required to Register', domain=[('model', '=', 'res.partner')],
        help="Fields that must be filled before a contact with this tag can be registered.")

    _sql_constraints = [
        ('registration_program_code_uniq', 'unique(registration_program_code)',
         'Another tag already uses this Record Search code.'),
    ]

    @api.model
    def _record_search_program(self, code):
        """The programme tag of a Record Search code (empty when unknown)."""
        if not code:
            return self.browse()
        return self.sudo().search([('registration_program_code', '=', code)], limit=1).sudo(False)

    @api.model
    def _link_program_menus(self, code, menu_xmlids):
        """Install / upgrade of a programme module: its menus follow the tag of
        its Record Search code (shown while the programme is enabled). Does
        nothing while no tag has that code."""
        tag = self._record_search_program(code).sudo()
        if not tag:
            return
        menus = self.env['ir.ui.menu'].sudo()
        for xmlid in menu_xmlids:
            menus |= self.env.ref(xmlid, raise_if_not_found=False) or self.env['ir.ui.menu']
        if menus - tag.program_menu_ids:
            tag.program_menu_ids = [(4, menu.id) for menu in menus]
        tag._sync_program_menus()

    def _sync_program_menus(self):
        for tag in self.sudo():
            show = bool(tag.registration_program_code and tag.registration_program_active)
            menus = tag.with_context(active_test=False).program_menu_ids
            changed = menus.filtered(lambda m: m.active != show)
            if changed:
                changed.write({'active': show})

    def write(self, vals):
        res = super().write(vals)
        if 'registration_program_active' in vals or 'registration_program_code' in vals:
            self._sync_program_menus()
        return res
