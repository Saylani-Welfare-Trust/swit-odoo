from odoo import models, fields


type_selection = [
    ('cow', 'Cow'),
    ('goat', 'Goat'),
]

option_selection = [
    ('hole', 'Hole'),
    ('line', 'Line'),
]


class TransferSlaughter(models.TransientModel):
    _name = 'transfer.slaughter'
    _description = "Transfer Slaughter"


    type = fields.Selection(selection=type_selection, string="Type", default="cow")
    option = fields.Selection(selection=option_selection, string="Option", default="cow")
    
    actual_qurbani_cow_slaughter_id = fields.Many2one('qurbani.cow.slaughter', string="Cow Slaughter")
    actual_cow_slaughter_location_id = fields.Many2one(related='actual_qurbani_cow_slaughter_id.slaughter_location_id', string="Cow Slaughter")
    
    cow_start_time = fields.Float(related='actual_qurbani_cow_slaughter_id.start_time', string="Start Time", store=True)
    cow_end_time = fields.Float(related='actual_qurbani_cow_slaughter_id.end_time', string="End Time", store=True)

    actual_qurbani_goat_slaughter_id = fields.Many2one('qurbani.cow.slaughter', string="Goat Slaughter")
    actual_goat_slaughter_location_id = fields.Many2one(related='actual_qurbani_goat_slaughter_id.slaughter_location_id', string="Goat Slaughter")
    
    goat_start_time = fields.Float(related='actual_qurbani_goat_slaughter_id.start_time', string="Start Time", store=True)
    goat_end_time = fields.Float(related='actual_qurbani_goat_slaughter_id.end_time', string="End Time", store=True)

    
    qurbani_cow_slaughter_id = fields.Many2one('qurbani.cow.slaughter', string="Cow Slaughter")
    qurbani_cow_slaughter_line_id = fields.Many2one('qurbani.cow.slaughter.line', string="Cow Slaughter Line")
    cow_slaughter_location_id = fields.Many2one(related='qurbani_cow_slaughter_id.slaughter_location_id', string="Location", store=True)
    cow_product_id = fields.Many2one(related='qurbani_cow_slaughter_line_id.product_id', string="Product", store=True)
    
    cow_qurbani_order_no = fields.Char(related='qurbani_cow_slaughter_line_id.qurbani_order_no', string="QO No.", store=True)
    cow_qurbani_order_line_no = fields.Char(related='qurbani_cow_slaughter_line_id.qurbani_order_line_no', string="QOL No.", store=True)
    cow_hissa_name = fields.Char(related='qurbani_cow_slaughter_line_id.hissa_name', string="Hissa Name", store=True)
    
    qurbani_goat_slaughter_id = fields.Many2one('qurbani.goat.slaughter', string="Goat Slaughter")
    goat_slaughter_location_id = fields.Many2one(related='qurbani_goat_slaughter_id.slaughter_location_id', string="Location", store=True)
    goat_product_id = fields.Many2one(related='qurbani_goat_slaughter_id.product_id', string="Product", store=True)


    goat_qurbani_order_no = fields.Char(related='qurbani_goat_slaughter_id.qurbani_order_no', string="QO No.", store=True)
    goat_qurbani_order_line_no = fields.Char(related='qurbani_goat_slaughter_id.qurbani_order_line_no', string="QOL No.", store=True)
    goat_hissa_name = fields.Char(related='qurbani_goat_slaughter_id.hissa_name', string="Hissa Name", store=True)