/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { ActionpadWidget } from "@point_of_sale/app/screens/product_screen/action_pad/action_pad";
import { FavorPopup } from "../favor_popup/favor_popup";

patch(ActionpadWidget.prototype, {
    async onFavorPopupClick() {
        await this.env.services.popup.add(FavorPopup);
    }
});