from odoo import models
from odoo.exceptions import UserError
from odoo.tools.translate import _

# 1. Store a reference to Odoo's original, core system unlink function
original_unlink = models.BaseModel.unlink

# 2. Define the absolute restriction function
def secure_global_unlink(self):
    """
    Hard blocks every record deletion across the entire Odoo database.
    Catches custom modules, base modules, and all user tiers.
    """
    # CRITICAL SYSTEM SAFETY NET: Prevent system-breaking backend background tasks from failing.
    # This keeps Odoo running smoothly while fully blocking users from deleting records.
    if self._transient or self._name in ['bus.bus', 'website.visitor']:
        return original_unlink(self)

    raise UserError(_("Record deletion is permanently disabled across the system. Use archiving instead."))

# 3. Inject the function directly into the core Odoo engine
models.BaseModel.unlink = secure_global_unlink