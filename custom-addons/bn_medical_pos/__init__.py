from . import models
from . import wizards

MAIN_POS_ACTIONS = ('point_of_sale.action_pos_config_kanban', 'point_of_sale.action_pos_config_tree')


def _uninstall_hook(env):
    """The main Point of Sale lists hide the medical counters (views/pos_actions.xml): show all again"""
    for xmlid in MAIN_POS_ACTIONS:
        action = env.ref(xmlid, raise_if_not_found=False)
        if action and 'is_medical_pos' in (action.domain or ''):
            action.domain = False
