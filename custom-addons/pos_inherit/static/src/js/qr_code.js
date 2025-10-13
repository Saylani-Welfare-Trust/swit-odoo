odoo.define('pos_inherit.models', function (require) {
    'use strict';

    const models = require('point_of_sale.models');
    const Order = models.Order;

    const super_export_for_printing = Order.prototype.export_for_printing;
    Order.prototype.export_for_printing = function () {
        let result = super_export_for_printing.apply(this, arguments);
        result.slaughter_qr = this.slaughter_qr || false;
        return result;
    };

    const super_init_from_JSON = Order.prototype.init_from_JSON;
    Order.prototype.init_from_JSON = function (json) {
        super_init_from_JSON.apply(this, arguments);
        this.slaughter_qr = json.slaughter_qr || false;
    };

    const super_export_as_JSON = Order.prototype.export_as_JSON;
    Order.prototype.export_as_JSON = function () {
        let json = super_export_as_JSON.apply(this, arguments);
        json.slaughter_qr = this.slaughter_qr || false;
        return json;
    };
});
