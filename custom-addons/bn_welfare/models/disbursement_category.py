from odoo import api, models, fields


class DisbursementCategory(models.Model):
    _name = 'disbursement.category'
    _description = 'Disbursement Category'


    name = fields.Char('Name')

    @api.model
    def _bn_adopt_master_setup_categories(self):
        """The In Kind / Cash categories used to be data of bn_master_setup.
        Databases that still have those records keep them (existing welfare
        lines point at them): they take over the bn_welfare xml ids, and the
        duplicates bn_welfare created next to them are merged into them.
        Runs on every install / upgrade; does nothing once done."""
        IMD = self.env['ir.model.data'].sudo()
        for name in ('disbursement_category_in_kind', 'disbursement_category_Cash'):
            old_xmlid = IMD.search([('module', '=', 'bn_master_setup'), ('name', '=', name)], limit=1)
            if not old_xmlid:
                continue
            old = self.sudo().browse(old_xmlid.res_id).exists()
            new_xmlid = IMD.search([('module', '=', 'bn_welfare'), ('name', '=', name)], limit=1)
            if old:
                new = self.sudo().browse(new_xmlid.res_id).exists() if new_xmlid else self.browse()
                # Rebind the xml id first: unlinking ``new`` drops its xml ids.
                if new_xmlid:
                    new_xmlid.write({'res_id': old.id, 'model': self._name})
                else:
                    IMD.create({'module': 'bn_welfare', 'name': name, 'model': self._name,
                                'res_id': old.id, 'noupdate': True})
                if new and new != old:
                    self._bn_repoint_category(new, old)
                    new.unlink()
            old_xmlid.unlink()

    def _bn_repoint_category(self, src, dest):
        """Point every stored many2one on ``src`` to ``dest``."""
        fields_ = self.env['ir.model.fields'].sudo().search([
            ('relation', '=', self._name), ('ttype', '=', 'many2one'), ('store', '=', True),
        ])
        for field in fields_:
            Model = self.env.get(field.model)
            if Model is None or Model._abstract or not Model._auto:
                continue
            records = Model.sudo().with_context(active_test=False).search([(field.name, '=', src.id)])
            if records:
                records.write({field.name: dest.id})
