/** @odoo-module **/
/* ERP Heritage - Dashboard Builder
 * In-canvas "Add filter": pick a model + a field, and a global filter appears
 * on the bar that re-scopes every widget whose model has that field. */

import { Component, useState, onWillStart } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";

export class AddFilterDialog extends Component {
    static template = "eh_board.AddFilterDialog";
    static components = { Dialog };
    static props = { dashboardId: Number, onAdded: Function, close: Function };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            model_id: false, field: "", name: "", models: [], fields: [],
            modelSearch: "",
        });
        onWillStart(async () => {
            const meta = await this.orm.call(
                "eh.board.dashboard", "get_builder_meta", [[this.props.dashboardId]]);
            this.state.models = meta.models;
        });
    }

    async onModelChange(ev) {
        this.state.model_id = parseInt(ev.target.value, 10) || false;
        this.state.field = "";
        if (this.state.model_id) {
            const res = await this.orm.call(
                "eh.board.dashboard", "get_model_fields",
                [[this.props.dashboardId], this.state.model_id]);
            this.state.fields = res.dimensions;
        }
    }

    // Match the search against BOTH the human name and the technical model.
    get filteredModels() {
        const q = (this.state.modelSearch || "").toLowerCase().trim();
        if (!q) return this.state.models;
        return this.state.models.filter(
            (m) => (m.name || "").toLowerCase().includes(q)
                || (m.model || "").toLowerCase().includes(q));
    }

    get canConfirm() {
        return !!(this.state.model_id && this.state.field);
    }

    async confirm() {
        const res = await this.orm.call("eh.board.dashboard", "add_filter",
            [[this.props.dashboardId], {
                model_id: this.state.model_id,
                field: this.state.field,
                name: this.state.name,
            }]);
        if (res && res.filter) {
            this.props.onAdded(res.filter);
        }
        this.props.close();
    }
}
