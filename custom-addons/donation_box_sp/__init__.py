# -*- coding: utf-8 -*-

from . import controllers
from . import models
from . import wizard


def uninstall_hook(env):
    keys_to_remove = [
        'donation_box_sp.gen_donation_req_picking',
        'donation_box_sp.donation_box_sp_type',
    ]
    for key in keys_to_remove:
        param = env['ir.config_parameter'].sudo().search([('key', '=', key)])
        if param:
            param.unlink()