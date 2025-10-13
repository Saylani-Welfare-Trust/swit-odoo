/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { useService } from "@web/core/utils/hooks";
import { useState, useRef, onMounted } from "@odoo/owl";
import { Numpad } from "@point_of_sale/app/generic_components/numpad/numpad";
import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";
import { usePos } from "@point_of_sale/app/store/pos_hook";


export class PaymentPopup extends NumberPopup {
    static template = "pos_enhancement.PaymentPopup";
    static components = { Numpad };
    static defaultProps = {
        confirmText: _t("Confirm"),
        cancelText: _t("Discard"),
        title: _t("Confirm?"),
        subtitle: "",
        body: "",
        cheap: false,
        startingValue: null,
        isPassword: false,
        nbrDecimal: 0,
        inputSuffix: "",
        getInputBufferReminder: () => false,
    };


    setup() {
        super.setup();
        this.pos = usePos();
        this.state.current_payment_method=false
        this.payment_methods_from_config = this.pos.payment_methods.filter((method) =>
            this.pos.config.payment_method_ids.includes(method.id)
        );
    }
    getPayload() {

        let startingPayload = null;
        if (typeof this.props.startingValue === "number" && this.props.startingValue > 0) {
            startingPayload = this.props.startingValue.toFixed(this.props.nbrDecimal);
        }
        if (this.state.payload != startingPayload) {
            return [this.state.payload, this.state.current_payment_method];
        }
        return [this.numberBuffer.get(),this.state.current_payment_method];
    }
    paymentMethodImage(id) {
        if (this.paymentMethod.image) {
            return `/web/image/pos.payment.method/${id}/image`;
        } else if (this.paymentMethod.type === "cash") {
            return "/point_of_sale/static/src/img/money.png";
        } else if (this.paymentMethod.type === "pay_later") {
            return "/point_of_sale/static/src/img/pay-later.png";
        } else {
            return "/point_of_sale/static/src/img/card-bank.png";
        }
    }
    confirm(event) {
        if (this.state.current_payment_method){
            super.confirm();
        }
    }
    addNewPaymentLine(paymentMethod) {
        this.state.current_payment_method=paymentMethod
    }
}
