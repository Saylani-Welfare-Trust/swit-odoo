/** @odoo-module **/

import { useService } from "@web/core/utils/hooks";
import { onMounted, useState } from "@odoo/owl";
import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";

export class QurbaniSchedule extends AbstractAwaitablePopup {
    static template = "bn_qurbani.QurbaniSchedule";

    setup() {
        super.setup();

        this.orm = useService("orm");

        this.state = useState({
            data: {},
            selectedCity: null,
            selectedLocation: null,
            selectedSlot: null,
        });

        onMounted(() => this.loadData());
    }

    async loadData() {
        this.state.data = await this.orm.call(
            "distribution.schedule",
            "get_distribution_details",
            []
        );
    }

    // CITY CHANGE
    onCityChange() {
        this.state.selectedLocation = null;
        this.state.selectedSlot = null;
    }

    // LOCATION CHANGE
    onLocationChange() {
        this.state.selectedSlot = null;
    }

    // ✅ FIXED SLOT SELECT (NO THIS ERROR)
    selectSlot(ev) {
        const slotId = parseInt(ev.currentTarget.dataset.id);

        const city = this.state.selectedCity;
        const location = this.state.selectedLocation;

        const slot = this.state.data?.[city]?.[location]
            ?.find(s => s.id === slotId);

        if (!slot || slot.remaining_hissa <= 0) return;

        this.state.selectedSlot = slot;
    }

    // CONFIRM
    confirmSelection() {
        const slot = this.state.selectedSlot;

        if (!slot) return;

        this.props.close({
            confirmed: true,
            payload: {
                city: this.state.selectedCity,
                location: this.state.selectedLocation,
                slot: slot,
            },
        });
    }

    // CANCEL
    cancel() {
        this.props.close({
            confirmed: false,
            payload: null,
        });
    }
}