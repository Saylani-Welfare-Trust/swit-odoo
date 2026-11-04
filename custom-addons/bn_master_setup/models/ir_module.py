# -*- coding: utf-8 -*-
import csv
import logging
import os

from lxml import etree

from odoo import api, models
from odoo.modules.module import get_manifest, get_module_path

_logger = logging.getLogger(__name__)

# Reflection of models and fields: the module that defines the model / field
# now creates its own external id for it.
# The old module's copy of such a record is deleted when the new module has its
# own record with the same id (otherwise it would stay, e.g. a view twice).
# Any other record (groups, data ...) is never deleted, only its id dropped.
DISPOSABLE_MODELS = (
    'ir.ui.view', 'ir.ui.menu', 'ir.actions.act_window', 'ir.actions.server',
    'ir.actions.report', 'ir.actions.client', 'ir.model.access', 'ir.rule', 'ir.cron',
)

REFLECTION_MODELS = (
    'ir.model', 'ir.model.fields', 'ir.model.fields.selection',
    'ir.model.constraint', 'ir.model.relation', 'ir.model.inherit',
)


def _declared_ids(module):
    """External ids (without module prefix) declared by the data files of ``module``."""
    path = get_module_path(module)
    ids = set()
    for name in (get_manifest(module) or {}).get('data', []):
        file = os.path.join(path, name)
        if not os.path.isfile(file):
            continue
        if name.endswith('.csv'):
            with open(file, newline='') as handle:
                rows = list(csv.reader(handle))
            ids.update(row[0] for row in rows[1:] if row)
        elif name.endswith('.xml'):
            for node in etree.parse(file).iter():
                xmlid = node.get('id') if isinstance(node.tag, str) else None
                if xmlid:
                    ids.add(xmlid)
    return {i.split('.', 1)[1] if i.startswith(module + '.') else i for i in ids if '.' not in i or i.startswith(module + '.')}


class IrModuleModule(models.Model):
    _inherit = 'ir.module.module'

    @api.model
    def _bn_absorb_modules(self, new, olds):
        """A module merged into ``new``: hand its records over before ``new``
        loads its data (call it from the first data file of ``new``).

        The views, groups, menus, actions, access rules, sequences ... keep
        their external ids (same name, module ``new``), so ``new`` updates them
        in place instead of creating a second copy, and what ``new`` no longer
        declares is removed at the end of its update. The old module is then
        marked uninstalled: its folder can be deleted. Nothing happens on a
        fresh install or once the old module is gone."""
        cr = self.env.cr
        done = []
        for old in olds:
            cr.execute("SELECT state FROM ir_module_module WHERE name = %s", [old])
            row = cr.fetchone()
            if not row or row[0] in ('uninstalled', 'uninstallable'):
                continue
            cr.execute("DELETE FROM ir_model_data WHERE module = %s AND model IN %s", [old, REFLECTION_MODELS])
            # an id the new module already has: the new module's record is kept
            cr.execute("""
                SELECT o.id, o.model, o.res_id FROM ir_model_data o
                  JOIN ir_model_data n ON n.module = %s AND n.name = o.name
                 WHERE o.module = %s AND (n.model != o.model OR n.res_id != o.res_id)
            """, [new, old])
            for data_id, model, res_id in cr.fetchall():
                if model in DISPOSABLE_MODELS and model in self.env:
                    try:
                        with cr.savepoint():
                            self.env[model].sudo().browse(res_id).exists().unlink()
                    except Exception as e:  # noqa: BLE001 - keep merging the rest
                        _logger.warning("Merge %s into %s: %s %s not removed: %s", old, new, model, res_id, e)
            cr.execute("""
                DELETE FROM ir_model_data o
                 WHERE o.module = %s
                   AND EXISTS (SELECT 1 FROM ir_model_data n WHERE n.module = %s AND n.name = o.name)
            """, [old, new])
            # views, menus, actions, access rights ... the new module does not declare
            # are removed now, before its views are checked (an old view calling a
            # method that no longer exists would stop the update)
            declared = _declared_ids(new)
            cr.execute("SELECT id, name, model, res_id FROM ir_model_data WHERE module = %s AND model IN %s",
                       [old, DISPOSABLE_MODELS])
            for data_id, name, model, res_id in cr.fetchall():
                if name in declared or model not in self.env:
                    continue
                if model == 'ir.actions.server' and name.endswith('_ir_actions_server') \
                        and name[:-len('_ir_actions_server')] in declared:
                    continue  # the action of a scheduled job the new module declares
                try:
                    with cr.savepoint():
                        self.env[model].sudo().browse(res_id).exists().unlink()
                        cr.execute("DELETE FROM ir_model_data WHERE id = %s", [data_id])
                except Exception as e:  # noqa: BLE001 - removed at the end of the update instead
                    _logger.warning("Merge %s into %s: %s %s not removed: %s", old, new, model, res_id, e)
            cr.execute("UPDATE ir_model_data SET module = %s WHERE module = %s", [new, old])
            moved = cr.rowcount
            cr.execute("UPDATE ir_module_module SET state = 'uninstalled', latest_version = NULL WHERE name = %s", [old])
            cr.execute("DELETE FROM ir_module_module_dependency WHERE name = %s", [old])
            _logger.info("Module %s merged into %s: %s records handed over", old, new, moved)
            done.append(old)
        if done:
            self.env.registry.clear_cache()
            self.env.invalidate_all()
        return done
