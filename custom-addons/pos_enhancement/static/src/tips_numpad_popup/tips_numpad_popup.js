/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { useService } from "@web/core/utils/hooks";
import { useState, useRef, onMounted } from "@odoo/owl";
import { Numpad } from "@point_of_sale/app/generic_components/numpad/numpad";
import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";


export class TipsNumpadPopup extends NumberPopup {
    static template = "qubit_pos_enhancement.TipsNumpadPopup";
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
        this.state.is_percent=this.props.is_percent
        // this.numberBuffer = useService("number_buffer");
        // this.numberBuffer.use({
        //     triggerAtEnter: () => this.confirm(),
        //     triggerAtEscape: () => this.cancel(),
        //     state: this.state,
        // });
        // this.inputRef = useRef("input");
        // onMounted(this.onMounted);
    }
    // onMounted() {
    //     if (this.inputRef.el) {
    //         this.inputRef.el.focus();
    //     }
    // }
    // get decimalSeparator() {
    //     return this.env.services.localization.decimalPoint;
    // }
    // getNumpadButtons() {
    //     const { isPassword, cheap } = this.props;
    //     return [
    //         { value: "1" },
    //         { value: "2" },
    //         { value: "3" },
    //         ...(!isPassword ? [{ value: cheap ? "+1" : "+10" }] : []),
    //         { value: "4" },
    //         { value: "5" },
    //         { value: "6" },
    //         ...(!isPassword ? [{ value: cheap ? "+2" : "+20" }] : []),
    //         { value: "7" },
    //         { value: "8" },
    //         { value: "9" },
    //         ...(!isPassword ? [{ value: "-" }] : []),
    //         { value: "Delete", text: "C" },
    //         { value: "0" },
    //         ...(!isPassword ? [{ value: this.decimalSeparator }] : []),
    //         { value: "Backspace", text: "⌫" },
    //     ];
    // }
    // get inputBuffer() {
    //     if (this.state.buffer === null) {
    //         return "";
    //     }
    //     if (this.props.isPassword) {
    //         return this.state.buffer.replace(/./g, "•");
    //     } else {
    //         return this.state.buffer;
    //     }
    // }
    // confirm(event) {
    //     if (this.numberBuffer.get() || this.state.payload) {
    //         super.confirm();
    //     }
    // }
    getPayload() {

        let startingPayload = null;
        if (typeof this.props.startingValue === "number" && this.props.startingValue > 0) {
            startingPayload = this.props.startingValue.toFixed(this.props.nbrDecimal);
        }
        // console.log(this.state)
        if (this.state.payload != startingPayload) {
            return [this.state.payload, this.state.is_percent];
        }
        return [this.numberBuffer.get(),this.state.is_percent];
    }
    // isMobile() {
    //     return window.innerWidth <= 768;
    // }
}
