/** @odoo-module */

import { Navbar } from "@point_of_sale/app/navbar/navbar";
import { patch } from "@web/core/utils/patch";

import { CustomClosingPopup } from "../app/closing_popup/custom_closing_popup";

patch(Navbar.prototype, {
    async closeSession() {
        // console.log(this);

        const info = await this.pos.getClosePosInfo();
        this.popup.add(CustomClosingPopup, { ...info });
    }
});