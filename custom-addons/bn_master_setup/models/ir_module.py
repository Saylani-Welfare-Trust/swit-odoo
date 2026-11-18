# -*- coding: utf-8 -*-
import csv
import logging
import os
import re

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


# Releases that merged modules which are their own modules again: the owner, the
# version it was installed at, and the modules it had taken over.
MERGED_BY = {
    'bn_master_setup': {'17.0.1.3.0': ['bn_res_company', 'bn_res_users', 'bn_res_currency',
                                       'bn_report_customization']},
    'bn_pos_cheque': {'17.0.1.3.0': ['bn_pos_payment_method', 'bn_journal_transfer']},
    'bn_procurement_finance': {'17.0.1.2.0': ['bn_payment_customization']},
    'bn_procurement_workflow': {'17.0.1.2.0': ['bn_purchase_audit']},
}


# External ids an earlier version named with "bn" (see _rename_xmlids); ids
# built from a module name keep it
_XMLID_RENAMES = {'mail_activity_type_bn_step': 'mail_activity_type_next_step'}


def _new_xmlid_name(name, modules):
    if name in _XMLID_RENAMES:
        return _XMLID_RENAMES[name]
    held = name
    for module in sorted(modules, key=len, reverse=True):
        held = re.sub(r'(?:(?<=_)|^)%s(?=_|$)' % re.escape(module), module.replace('bn_', '\x00'), held)
    held = re.sub(r'^bn_', '', held)
    held = re.sub(r'_bn_', '_', held)
    held = re.sub(r'_bn$', '', held)
    return held.replace('\x00', 'bn_')


class IrModuleModule(models.Model):
    _inherit = 'ir.module.module'

    @api.model
    def _rename_xmlids(self):
        """External ids renamed in this version (search views, the next-step
        activity type ...) are renamed in place before the modules load them
        under their new name, so records keep their data and no old view is
        left behind. Only when the module declares the new id."""
        cr = self.env.cr
        cr.execute("SELECT name FROM ir_module_module WHERE name LIKE 'bn\\_%%'")
        modules = [row[0] for row in cr.fetchall()]
        cr.execute("""SELECT id, module, name, model, res_id FROM ir_model_data
                       WHERE module LIKE 'bn\\_%%' AND name ~ '(^|_)bn(_|$)'""")
        declared, renamed = {}, 0
        for data_id, module, name, model, res_id in cr.fetchall():
            if module not in declared:
                declared[module] = _declared_ids(module) if get_module_path(module) else set()
            new = _new_xmlid_name(name, modules)
            if new == name or new not in declared[module]:
                continue
            cr.execute("SELECT res_id FROM ir_model_data WHERE module = %s AND name = %s", [module, new])
            row = cr.fetchone()
            if row:
                # both exist (an interrupted update): what uses the old record
                # moves to the new one, the old one is then removed as usual
                self._merge_renamed_record(model, res_id, row[0])
                continue
            cr.execute("UPDATE ir_model_data SET name = %s WHERE id = %s", [new, data_id])
            renamed += 1
        if renamed:
            _logger.info("%s external ids renamed", renamed)
            self.env.registry.clear_cache()

    @api.model
    def _merge_renamed_record(self, model, old_id, new_id):
        cr = self.env.cr
        if old_id == new_id:
            return
        if model == 'mail.activity.type':
            cr.execute("UPDATE mail_activity SET activity_type_id = %s WHERE activity_type_id = %s", [new_id, old_id])
            cr.execute("UPDATE mail_message SET mail_activity_type_id = %s WHERE mail_activity_type_id = %s",
                       [new_id, old_id])
        elif model == 'res.groups':
            cr.execute("""INSERT INTO res_groups_users_rel (gid, uid)
                          SELECT %s, uid FROM res_groups_users_rel WHERE gid = %s ON CONFLICT DO NOTHING""",
                       [new_id, old_id])
        elif model == 'ir.module.category':
            cr.execute("UPDATE res_groups SET category_id = %s WHERE category_id = %s", [new_id, old_id])

    @api.model
    def _remove_records(self, xmlids):
        """Remove records a module no longer declares but that Odoo keeps
        because they were loaded as noupdate (e.g. a dropped group)."""
        for xmlid in xmlids:
            record = self.env.ref(xmlid, raise_if_not_found=False)
            if record:
                record.sudo().unlink()
                _logger.info("Removed %s (no longer used)", xmlid)

    @api.model
    def _release_merged_modules(self):
        """Database updated with a release that merged modules which are now
        their own modules again (MERGED_BY): give each its records back and
        install it again. Runs first in bn_master_setup, before the owners are
        updated (their installed version is still the merging one). A module
        uninstalled on purpose is left alone: only one the owner took over is
        installed again."""
        cr = self.env.cr
        released = []
        for owner, by_version in MERGED_BY.items():
            cr.execute("SELECT latest_version FROM ir_module_module WHERE name = %s AND state != 'uninstalled'", [owner])
            row = cr.fetchone()
            olds = by_version.get(row[0]) if row else None
            for old in olds or []:
                cr.execute("SELECT state FROM ir_module_module WHERE name = %s", [old])
                state = cr.fetchone()
                if not state or state[0] != 'uninstalled' or not get_module_path(old):
                    continue
                # the records the owner took over carry the owner's module name
                names = _declared_ids(old)
                if names:
                    cr.execute("""SELECT id, model, res_id FROM ir_model_data
                                   WHERE module = %s AND name IN %s""", [owner, tuple(names)])
                    for data_id, model, res_id in cr.fetchall():
                        if model == 'ir.ui.view':
                            # its fields are back only once the module is installed:
                            # the view is loaded again from its data file
                            with cr.savepoint():
                                self.env['ir.ui.view'].sudo().browse(res_id).exists().unlink()
                            cr.execute("DELETE FROM ir_model_data WHERE id = %s", [data_id])
                        else:
                            cr.execute("UPDATE ir_model_data SET module = %s WHERE id = %s", [old, data_id])
                self.search([('name', '=', old)]).button_install()
                released.append(old)
                _logger.info("Module %s, merged into %s by version %s, is installed again", old, owner, row[0])
        if released:
            self.env.registry.clear_cache()
        return released

    @api.model
    def _absorb_modules(self, new, olds):
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
