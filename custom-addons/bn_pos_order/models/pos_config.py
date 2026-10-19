from odoo import models, fields, api
import re

class PosConfig(models.Model):
    _inherit = 'pos.config'

    branch_name = fields.Char(string="Branch Name", compute="_compute_branch_info", store=True)
    branch_code = fields.Char(string="Branch Code", compute="_compute_branch_info", store=True)

    @api.depends('name')
    def _compute_branch_info(self):
        for config in self:
            if not config.name:
                config.branch_name = False
                config.branch_code = False
                continue

            name = config.name.strip()
            
            # 1. Extract the Code (Looks for digits at the very beginning of the name)
            # This works for "9649 - ...", "567-...", or "9649 HEAD OFFICE"
            code_match = re.match(r'^(\d+)', name)
            if code_match:
                config.branch_code = code_match.group(1)
            else:
                config.branch_code = False

            # 2. Extract the Branch Name
            # Split by hyphen and remove empty spaces
            parts = [p.strip() for p in name.split('-') if p.strip()]
            
            if len(parts) >= 2:
                # If there are hyphens, the last part is usually the branch name
                # (e.g., "HEAD OFFICE (KARACHI)")
                config.branch_name = parts[-1]
            else:
                # If there are NO hyphens, use the whole name, 
                # but safely remove the leading code if we found one earlier.
                if config.branch_code:
                    # Removes "9649" and any leftover spaces/hyphens from the start
                    clean_name = re.sub(r'^\d+\s*-?\s*', '', name)
                    config.branch_name = clean_name.strip()
                else:
                    config.branch_name = name