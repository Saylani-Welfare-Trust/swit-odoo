# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, exceptions, models
from odoo.addons.phone_validation.tools import phone_validation


class BaseModel(models.AbstractModel):
    _inherit = 'base'


    def _phone_format(self, fname=False, number=False, country=False, force_format='E164', raise_exception=False):
        return number
