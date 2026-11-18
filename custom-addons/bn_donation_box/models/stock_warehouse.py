# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    donation_box_picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Donation Box Operation Type',
        copy=False,
        check_company=True,
        domain="['|', ('warehouse_id', '=', id), ('warehouse_id', '=', False)]",
        help="Default operation type used by Donation Box requests of this warehouse "
             "(Receipt, Delivery, Internal Transfer or any other type). The source and "
             "destination locations of the transfer are taken from this operation type.",
    )

    @api.constrains('donation_box_picking_type_id')
    def _check_donation_box_picking_type_id(self):
        for warehouse in self:
            picking_type = warehouse.donation_box_picking_type_id
            if picking_type and picking_type.warehouse_id and picking_type.warehouse_id != warehouse:
                raise ValidationError(_(
                    'The operation type "%(type)s" belongs to warehouse "%(other)s" and '
                    'cannot be the Donation Box operation type of warehouse "%(this)s".'
                ) % {
                    'type': picking_type.display_name,
                    'other': picking_type.warehouse_id.display_name,
                    'this': warehouse.display_name,
                })

    def action_create_donation_box_picking_type(self):
        """Create (once) a dedicated 'Donation Box' internal operation type for the
        warehouse, together with its 'Donation Box' destination location, and set it
        as the warehouse default."""
        self.ensure_one()
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise UserError(_('Only Inventory Administrators can configure warehouse operation types.'))
        if self.donation_box_picking_type_id:
            raise UserError(_('This warehouse already has a Donation Box operation type.'))

        Location = self.env['stock.location']
        location = Location.search([
            ('name', '=', 'Donation Box'),
            ('location_id', '=', self.view_location_id.id),
            ('usage', '=', 'customer'),
        ], limit=1)
        if not location:
            location = Location.create({
                'name': 'Donation Box',
                'usage': 'customer',
                'location_id': self.view_location_id.id,
                'company_id': self.company_id.id,
            })

        picking_type = self.env['stock.picking.type'].create({
            'name': _('Donation Box'),
            'code': 'internal',
            'sequence_code': 'DBOX',
            'warehouse_id': self.id,
            'company_id': self.company_id.id,
            'default_location_src_id': self.lot_stock_id.id,
            'default_location_dest_id': location.id,
            'use_create_lots': False,
            'use_existing_lots': True,
        })
        self.donation_box_picking_type_id = picking_type
        return True

    @api.model
    def _bn_migrate_legacy_donation_box_type(self):
        """Bind the historical global 'Donation Box' operation type (created by
        bn_donation_box's data file, without any warehouse) to the warehouse it
        actually serves, and make it that warehouse's default.  Idempotent."""
        legacy = self.env.ref('bn_donation_box.donation_box_stock_picking_type', raise_if_not_found=False)
        if not legacy:
            return
        warehouse = legacy.warehouse_id
        if not warehouse:
            source = legacy.default_location_src_id
            warehouse = source.warehouse_id if source else self.browse()
            if not warehouse and source:
                warehouse = self.search([('lot_stock_id', '=', source.id)], limit=1)
            if warehouse:
                legacy.sudo().write({'warehouse_id': warehouse.id})
                _logger.info('Donation Box operation type %s bound to warehouse %s.',
                             legacy.display_name, warehouse.display_name)
        if warehouse and not warehouse.donation_box_picking_type_id:
            warehouse.donation_box_picking_type_id = legacy
