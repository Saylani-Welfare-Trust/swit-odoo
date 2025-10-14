/** @odoo-module **/

import { Order, Product } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import {
    formatFloat,
    roundDecimals as round_di,
    roundPrecision as round_pr,
    floatIsZero,
} from "@web/core/utils/numbers";


patch(Order.prototype, {
    setup(_defaultObj, options) {
        this.is_registered_order = options.is_registered_order || false; 
        this.order_type = options.order_type || 'one_time'; 
        this.in_kind_transaction_type = options.in_kind_transaction_type || false; 
        this.cash_transaction_type = options.cash_transaction_type || false; 
        this.disbursement_type = options.disbursement_type || false; 
        this.barcode = options.barcode || false; 
        this.analytic_account_ids= options.analytic_account_ids || [];
        this.reprint_support = options.reprint_support || 'no_limit';
        this.description = options.description|| '';
        super.setup(...arguments); 
    },

    export_as_JSON() {
        const json = super.export_as_JSON(); 
        json.order_type = this.order_type;
        json.in_kind_transaction_type = this.in_kind_transaction_type;
        json.cash_transaction_type = this.cash_transaction_type;
        json.disbursement_type = this.disbursement_type;
        json.barcode = this.barcode;
        json.analytic_account_ids = this.analytic_account_ids;
        json.reprint_support = this.reprint_support;
        json.description = this.description;

        return json;
    },
    init_from_JSON(json) {
        this.order_type = json.order_type || null; 
        this.in_kind_transaction_type = json.in_kind_transaction_type || null; 
        this.disbursement_type = json.disbursement_type || null; 
        this.barcode = json.barcode || null; 
        this.analytic_account_ids = json.analytic_account_ids || [];
        this.reprint_support = json.reprint_support || 'no_limit';
        this.description = json.description || '';
        super.init_from_JSON(json); 
    },

    add_analytic_account(analytic_account) {
        if (this.analytic_account_ids.find((t) => t.id === analytic_account.id)){
            return
        }
        this.analytic_account_ids.push(analytic_account);
    },
    remove_analytic_account(analytic_account) {
        this.analytic_account_ids = this.analytic_account_ids.filter((t) => t.id !== analytic_account.id);
    },
    set_order_type(order_type) {
        this.order_type = order_type;
        
    },
    set_disbursement_type(disbursement_type) {
        this.disbursement_type = disbursement_type;
    },
    set_in_kind_transaction_type(in_kind_transaction_type) {
        this.in_kind_transaction_type = in_kind_transaction_type;
    },
    set_cash_transaction_type(cash_transaction_type) {
        this.cash_transaction_type = cash_transaction_type;
    },
    set_reprint_support(reprint_support) {
        this.reprint_support = reprint_support;
    },
    set_barcode(barcode) {
        this.barcode = barcode;
    },
    set_descrition(description) {
        this.description = description;
    },
    export_for_printing() {
        const values= {
            ...super.export_for_printing(...arguments),
            order_type: this.order_type,
            disbursement_type: this.disbursement_type,
            in_kind_transaction_type: this.in_kind_transaction_type,
            cash_transaction_type: this.cash_transaction_type,
            barcode: this.barcode,
            description: this.description
        };
        return values
    },
    get_total_without_tax() {
        if (this.get_partner()?.is_donee) {
            // console.log('this.orderLine',this.orderLine)
            // if (Array.isArray(this.orderLine)) {
                return round_pr(
                    this.orderlines.filter((line) => line.product.is_subsidised).reduce(function (sum, orderLine) {
                        return sum + orderLine.get_price_without_tax();
                    }, 0),
                    this.pos.currency.rounding
                );
            // } 
            // else {
            //     return 0;  
            // }
        }
        return super.get_total_without_tax();
    }





});


patch(Product.prototype, {

});

