///** @odoo-module **/
//
//import { registry } from "@web/core/registry";
//import { CharField } from "@web/views/fields/char/char_field";
//
//export class CNICField extends CharField {
//    setup() {
//        super.setup();
//        this.onInput = this.onInput.bind(this);
//    }
//
//    onInput(ev) {
//        let value = ev.target.value.replace(/\D/g, ""); // Remove all non-digits
//        if (value.length > 5) value = value.slice(0, 5) + "-" + value.slice(5);
//        if (value.length > 13) value = value.slice(0, 13) + "-" + value.slice(13, 14);
//        ev.target.value = value;
//        this._setValue(ev.target.value);
//    }
//
//    mounted() {
//        super.mounted();
//        this.el.addEventListener("input", this.onInput);
//    }
//
//    willUnmount() {
//        this.el.removeEventListener("input", this.onInput);
//        super.willUnmount();
//    }
//}
//
//registry.category("fields").add("cnic_format", CNICField);
