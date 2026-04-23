/** @odoo-module **/

import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { onMounted, useState } from "@odoo/owl";
import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";

export class QurbaniSchedule extends AbstractAwaitablePopup {
    static template = "bn_qurbani.QurbaniSchedule";

    setup() {
        super.setup();

        this.pos = usePos();
        this.orm = useService("orm");
        this.notification = useService("notification");
        
        this.product = this.props.product || false;

        this.state = useState({
            data: {},
            selectedCity: null,
            selectedLocation: null,
            selectedSlot: null,
            selectedSlotId: null,   // ✅ ADDED
            name: "",
        });

        this.defaultCity = this.pos.config.city_id?.[1]?.split('/')?.pop() || "";
        this.defaultLocation = this.pos.config.distribution_id?.[1]?.split('/')?.pop() || "";

        onMounted(() => this.loadData());
    }

    async loadData() {
        const productId = this.product.id;

        this.state.data = await this.orm.call(
            "distribution.schedule",
            "get_distribution_details",
            [productId]
        );

        if (this.defaultCity && this.state.data[this.defaultCity]) {
            this.state.selectedCity = this.defaultCity;

            if (this.defaultLocation &&
                this.state.data[this.defaultCity][this.defaultLocation]) {
                this.state.selectedLocation = this.defaultLocation;
            }
        }
    }

    onCityChange() {
        this.state.selectedLocation = null;
        this.state.selectedSlot = null;
        this.state.selectedSlotId = null;   // ✅ RESET
    }

    onLocationChange() {
        this.state.selectedSlot = null;
        this.state.selectedSlotId = null;   // ✅ RESET
    }

    selectSlot(ev) {
        const slotId = parseInt(ev.currentTarget.dataset.id);

        const city = this.state.selectedCity;
        const location = this.state.selectedLocation;

        const slot = this.state.data?.[city]?.[location]
            ?.find(s => s.id === slotId);

        if (!slot || slot.remaining_hissa <= 0) return;

        this.state.selectedSlotId = slotId;   // ✅ for UI highlight

        this.state.selectedSlot = {
            id: slot.id,
            slaughter: {
                location: slot.slaughter_location_id,
                start: slot.slaughter_start_time,
                end: slot.slaughter_end_time,
            },
            distribution: {
                location: slot.distribution_location_id,
                start: slot.distribution_start_time,
                end: slot.distribution_end_time,
            },
            remaining_hissa: slot.remaining_hissa,
            product: slot.product,
            day: slot.day,
        };
    }

    validateName(name) {
        const regex = /^[A-Za-z ]{3,}$/;
        return regex.test(name.trim());
    }

    onNameInput(ev) {
        this.state.name = ev.target.value;
    }

    confirmSelection() {
        const slot = this.state.selectedSlot;
        const name = this.state.name?.trim();

        if (!slot) return;

        if (!this.validateName(name)) {
            this.notification.add(
                "Name must be at least 3 characters and contain only letters.",
                { type: "warning" }
            );
            return;
        }

        this.props.close({
            confirmed: true,
            payload: {
                name,
                city: this.state.selectedCity,
                location: this.state.selectedLocation,
                slot,
            },
        });
    }

    cancel() {
        this.props.close({
            confirmed: false,
            payload: null,
        });
    }
}