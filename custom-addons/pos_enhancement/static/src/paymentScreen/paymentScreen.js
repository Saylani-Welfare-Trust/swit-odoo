/** @odoo-module **/

import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { Many2manyFieldTags } from "../many2many_field_tags/many2many_field_tags";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";


patch(PaymentScreen, {
    components: {
        ...PaymentScreen.components,
        Many2manyFieldTags
    }
})

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        console.log(this.components);
    },
    get is_donee(){
        const partner = this.currentOrder.get_partner();
        if (partner){
            return partner.is_donee
        }
        return false
    },
    async validateOrder(isForceValidate) {
        this.numberBuffer.capture();
        if (this.pos.config.cash_rounding) {
            if (!this.pos.get_order().check_paymentlines_rounding()) {
                this.popup.add(ErrorPopup, {
                    title: _t("Rounding error in payment lines"),
                    body: _t(
                        "The amount of your payment lines must be rounded to validate the transaction."
                    ),
                });
                return;
            }
        }
        if (await this._isOrderValid(isForceValidate)) {
            // remove pending payments before finalizing the validation
            for (const line of this.paymentLines) {
                if (!line.is_done()) {
                    this.currentOrder.remove_paymentline(line);
                }
            }
            await this._finalizeValidation();
        }
    },
    async _isOrderValid(isForceValidate) {
        if (!this.is_donee) return super._isOrderValid(isForceValidate)
            
        if (this.currentOrder.get_orderlines().length === 0 && this.currentOrder.is_to_invoice()) {
            this.popup.add(ErrorPopup, {
                title: _t("Empty Order"),
                body: _t(
                    "There must be at least one product in your order before it can be validated and invoiced."
                ),
            });
            return false;
        }
        const partner = this.currentOrder.get_partner();
        console.log(partner)
        if (!partner){
            this.popup.add(ErrorPopup, {
                title: _t("Donee is not Selected"),
                body: _t(
                    "Please Select Donee Before Validate."
                ),
            });
            return false;
            
        }
        if (!this.currentOrder.order_type){
            this.popup.add(ErrorPopup, {
                title: _t("Order Type is not Selected"),
                body: _t(
                    "Please Select Order Type Before Validate."
                ),
            });
            return false;
            
        }
        if (!this.currentOrder.disbursement_type){
            this.popup.add(ErrorPopup, {
                title: _t("Disbursement is not Selected"),
                body: _t(
                    "Please Select Disbursement Before Validate."
                ),
            });
            return false;
            
        }
        const transaction_type = this.currentOrder.disbursement_type === 'in_kind' ? this.currentOrder.in_kind_transaction_type : this.currentOrder.cash_transaction_type 

        if (!transaction_type){
            this.popup.add(ErrorPopup, {
                title: _t("Transaction type is not Selected"),
                body: _t(
                    "Please Select Transaction Type Before Validate."
                ),
            });
            return false;
            
        }

        if (!this.currentOrder._isValidEmptyOrder()) {
            return false;
        }

        return true;
    },
    setOrderType(e){
        this.currentOrder.set_order_type(e.target.value);
        this.pos.db.add_order(this.currentOrder.export_as_JSON());
    },
    
    setdisbursementType(e){
        this.currentOrder.set_disbursement_type(e.target.value);
        this.pos.db.add_order(this.currentOrder.export_as_JSON());
    },
    setInKindTransactionType(e){
        this.currentOrder.set_in_kind_transaction_type(e.target.value);
        this.pos.db.add_order(this.currentOrder.export_as_JSON());
    },
    setCashTransactionType(e){
        this.currentOrder.set_cash_transaction_type(e.target.value);
        this.pos.db.add_order(this.currentOrder.export_as_JSON());
    },
    setReprintSupport(e){
        this.currentOrder.set_reprint_support(e.target.value);
        this.pos.db.add_order(this.currentOrder.export_as_JSON());
    },
    setDescrition(e){
        this.currentOrder.set_descrition(e.target.value);
        this.pos.db.add_order(this.currentOrder.export_as_JSON());
    },
    get is_susidised(){
        let is_susidised = false
        this.currentOrder.orderlines.forEach(line => {
            console.log("is_susidised true",line.product,line.product.is_subsidised)
            if(line.product.is_subsidised){
                is_susidised = true
                // return true
            }
        });
        // console.log("is_susidised false",line.product,line.product.is_susidised)
        return is_susidised
    }

});
