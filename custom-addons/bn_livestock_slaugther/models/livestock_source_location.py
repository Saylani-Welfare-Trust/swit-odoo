from odoo import _, api, fields, models

# where livestock lines come from (livestock.slaugther._livestock_source)
LIVESTOCK_SOURCES = [
    ('pos', 'POS Order'),
    ('dhs', 'Donation Home Service'),
    ('direct_deposit', 'Direct Deposit'),
    ('donation', 'Import Donation'),
    ('api_donation', 'API Donation'),
    ('advance_donation', 'Advance Donation'),
]


class LivestockSourceLocation(models.Model):
    """Master Setup > Livestock Locations: one row per module livestock comes from.
    A Location set on a row: every livestock line from that module lands there (its
    Source and starting Destination Location) and waits there for slaughter. Empty:
    the module's default location."""
    _name = 'livestock.source.location'
    _description = 'Livestock Source Location'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    source = fields.Selection(LIVESTOCK_SOURCES, string='Module', required=True, readonly=True)
    default_location = fields.Char('Default Location', compute='_compute_default_location')
    location_id = fields.Many2one(
        'stock.location', string='Location', domain="[('usage', 'in', ('internal', 'transit'))]",
        help="Where the livestock from this module lands and waits for slaughter. "
             "Empty: the default location.")

    _sql_constraints = [('source_unique', 'unique(source)', 'One row per module.')]

    @api.depends('source')
    def _compute_default_location(self):
        for row in self:
            row.default_location = (
                _("The location of the POS shop") if row.source in ('pos', 'dhs')
                else _("The Livestock Inflow Location of the warehouse (Livestock Warehouse Locations)"))

    @api.model
    def _location_for(self, source):
        """The location set for ``source`` (empty: none set)."""
        if not source:
            return self.env['stock.location']
        return self.sudo().search([('source', '=', source)], limit=1).location_id.sudo(False)
