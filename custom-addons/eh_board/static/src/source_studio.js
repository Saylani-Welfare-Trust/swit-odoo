/** @odoo-module **/
/* Unified in-canvas data-source studio: file upload, record-rule-safe join,
 * and admin-only read-only SQL. No navigation to backend configuration. */

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { Many2XAutocomplete } from "@web/views/fields/relational_utils";
import { useService } from "@web/core/utils/hooks";

const READONLY_MODEL_ACTIONS = { create: false, createEdit: false, write: false };

export class SourceStudio extends Component {
    static template = "eh_board.SourceStudio";
    static components = { Dialog, Many2XAutocomplete };
    static props = {
        dashboardId: Number,
        models: Array,
        canSql: Boolean,
        onCreated: Function,
        close: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.file = null;
        this.state = useState({
            provider: "file", name: "", filename: "", saving: false,
            left_model_id: false, right_model_id: false,
            leftFields: [], rightFields: [],
            left_key: "", right_key: "",
            left_agg: "count", right_agg: "count",
            left_value: "", right_value: "",
            left_label: "Left", right_label: "Right",
            query: "",
        });
    }

    setProvider(provider) {
        if (provider === "sql" && !this.props.canSql) return;
        this.state.provider = provider;
    }

    modelProps(side) {
        const id = this.state[`${side}_model_id`];
        const model = this.props.models.find((candidate) => candidate.id === id);
        return {
            activeActions: READONLY_MODEL_ACTIONS,
            fieldString: side === "left" ? "Left model" : "Right model",
            getDomain: () => [["id", "in", this.props.models.map((item) => item.id)]],
            id: `eh_board_source_${side}_model`,
            placeholder: "Search name or technical model...",
            quickCreate: null,
            resModel: "ir.model",
            searchLimit: 20,
            update: (records) => this.onModelSelected(side, records),
            value: model ? `${model.name} (${model.model})` : "",
        };
    }

    async onModelSelected(side, records) {
        const record = Array.isArray(records) && records.length ? records[0] : null;
        const modelId = record ? parseInt(record.id, 10) || false : false;
        this.state[`${side}_model_id`] = modelId;
        this.state[`${side}_key`] = "";
        this.state[`${side}_value`] = "";
        this.state[`${side}Fields`] = [];
        if (!modelId) return;
        const result = await this.orm.call("eh.board.dashboard", "get_model_fields",
            [[this.props.dashboardId], modelId]);
        if (this.state[`${side}_model_id`] === modelId) {
            this.state[`${side}Fields`] = result.columns || [];
        }
    }

    numericFields(side) {
        return this.state[`${side}Fields`].filter((field) =>
            ["integer", "float", "monetary"].includes(field.ttype));
    }

    onFile(ev) {
        this.file = ev.target.files && ev.target.files[0];
        this.state.filename = this.file ? this.file.name : "";
        if (this.file && !this.state.name) {
            this.state.name = this.file.name.replace(/\.[^.]+$/, "");
        }
    }

    get canConfirm() {
        if (this.state.provider === "file") return !!this.file;
        if (this.state.provider === "sql") return this.props.canSql && !!this.state.query.trim();
        const s = this.state;
        const leftValueOk = s.left_agg === "count" || !!s.left_value;
        const rightValueOk = s.right_agg === "count" || !!s.right_value;
        return !!(s.left_model_id && s.right_model_id && s.left_key && s.right_key
            && leftValueOk && rightValueOk);
    }

    async _fileBase64() {
        if (!this.file || this.file.size > 20 * 1024 * 1024) {
            throw new Error("Dashboard files are limited to 20 MB.");
        }
        const bytes = new Uint8Array(await this.file.arrayBuffer());
        const chunks = [];
        for (let i = 0; i < bytes.length; i += 0x8000) {
            chunks.push(String.fromCharCode(...bytes.subarray(i, i + 0x8000)));
        }
        return browser().btoa(chunks.join(""));
    }

    async confirm() {
        if (!this.canConfirm || this.state.saving) return;
        this.state.saving = true;
        try {
            const s = this.state;
            const vals = { provider: s.provider, name: s.name || undefined };
            if (s.provider === "file") {
                vals.filename = this.file.name;
                vals.data = await this._fileBase64();
            } else if (s.provider === "join") {
                Object.assign(vals, {
                    left_model_id: s.left_model_id, right_model_id: s.right_model_id,
                    left_key: s.left_key, right_key: s.right_key,
                    left_agg: s.left_agg, right_agg: s.right_agg,
                    left_value: s.left_value, right_value: s.right_value,
                    left_label: s.left_label, right_label: s.right_label,
                });
            } else {
                vals.query = s.query;
            }
            const source = await this.orm.call(
                "eh.board.dashboard", "create_builder_source",
                [[this.props.dashboardId], vals]);
            this.props.onCreated(source);
            this.props.close();
        } catch (error) {
            this.notification.add(error.message || String(error), { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }
}

// Kept behind a tiny seam, matching BoardAction, so browser APIs stay easy to
// patch in Odoo tours while avoiding a module-global identifier at click time.
function browser() {
    return window;
}
