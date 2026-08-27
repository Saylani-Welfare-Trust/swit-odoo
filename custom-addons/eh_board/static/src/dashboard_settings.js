/** @odoo-module **/
/* ERP Heritage - Dashboard Builder
 * Dashboard-level settings panel: name, visibility/sharing, palette, density,
 * default date range, auto-refresh and email digest. Owner / builder only.
 * A plain Dialog over the board so settings are always one click away. */

import { Component, useState, onWillStart } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";

const UNIT_SECONDS = { seconds: 1, minutes: 60, hours: 3600 };

export class DashboardSettings extends Component {
    static template = "eh_board.DashboardSettings";
    static components = { Dialog };
    static props = {
        dashboardId: Number,
        onSaved: Function,
        close: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            loading: true, saving: false, s: {}, users: [], canEdit: false,
            refreshValue: 1, refreshUnit: "minutes",
            search: { shared_user_ids: "", digest_user_ids: "" },
        });
        onWillStart(async () => {
            const s = await this.orm.call(
                "eh.board.dashboard", "get_settings", [[this.props.dashboardId]]);
            this.state.s = s;
            this.state.users = s.users || [];
            this.state.canEdit = !!s.can_edit;
            this._splitInterval(s.refresh_interval || 60);
            this.state.loading = false;
        });
    }

    // -- auto-refresh value + unit <-> seconds -------------------------------
    _splitInterval(secs) {
        // Show the friendliest unit: whole hours, else whole minutes, else seconds.
        if (secs % 3600 === 0) { this.state.refreshValue = secs / 3600; this.state.refreshUnit = "hours"; }
        else if (secs % 60 === 0) { this.state.refreshValue = secs / 60; this.state.refreshUnit = "minutes"; }
        else { this.state.refreshValue = secs; this.state.refreshUnit = "seconds"; }
    }
    get intervalSeconds() {
        const v = Math.max(1, parseInt(this.state.refreshValue, 10) || 1);
        return v * (UNIT_SECONDS[this.state.refreshUnit] || 1);
    }

    // -- people picker (search + click to add, chip to remove) --------------
    userName(id) {
        const u = this.state.users.find((x) => x.id === id);
        return u ? u.name : "#" + id;
    }
    selectedUsers(key) {
        return (this.state.s[key] || []).map((id) => ({ id, name: this.userName(id) }));
    }
    filteredUsers(key) {
        const q = (this.state.search[key] || "").toLowerCase().trim();
        const chosen = new Set(this.state.s[key] || []);
        return this.state.users.filter((u) =>
            !chosen.has(u.id) && (!q || u.name.toLowerCase().includes(q)));
    }
    toggleUser(key, id) {
        if (!this.state.canEdit) return;
        const cur = this.state.s[key] || [];
        this.state.s[key] = cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id];
    }

    async save() {
        if (!this.state.canEdit) return;
        this.state.saving = true;
        const s = this.state.s;
        const vals = {
            name: s.name,
            description: s.description || "",
            published: !!s.published,
            palette: s.palette,
            density: s.density,
            default_date_preset: s.default_date_preset,
            refresh_mode: s.refresh_mode,
            refresh_interval: this.intervalSeconds,
            digest_enabled: !!s.digest_enabled,
            shared_user_ids: s.shared_user_ids || [],
            digest_user_ids: s.digest_user_ids || [],
        };
        try {
            const saved = await this.orm.call(
                "eh.board.dashboard", "save_settings", [[this.props.dashboardId], vals]);
            this.props.onSaved(saved);
            this.props.close();
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "danger" });
        }
        this.state.saving = false;
    }
}
