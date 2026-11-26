/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useRef, useState, useEffect } from "@odoo/owl";
import { loadJS, loadBundle } from "@web/core/assets";

export class LivestockDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");

        this.trendRef = useRef("trendChart");
        this.deptRef = useRef("deptChart");
        this.stateRef = useRef("stateChart");
        this.sourceRef = useRef("sourceChart");

        const today = new Date();
        this.state = useState({
            data: null,
            loading: true,
            date_from: this._iso(new Date(today.getFullYear(), 0, 1)),
            date_to: this._iso(today),
            active_preset: "ytd",
            department: "",
            
            // Location hierarchy filters
            province_id: null,
            city_id: null,
            zone_id: null,
            segment_l1: null,
            segment_l2: null,
            segment_l3: null,
            segment_l4: null,
            segment_type: "",
            provinces: [],
            cities: [],
            zones: [],
            segments_l1: [],
            segments_l2: [],
            segments_l3: [],
            segments_l4: [],
        });

        this.charts = {};

        onWillStart(async () => {
            await this._loadChartJs();
            await this.fetch_dropdowns();
            await this.loadData();
        });

        useEffect(() => {
            if (this.state.loading || !this.state.data) {
                this._destroyCharts();
                return;
            }
            this.renderCharts();
            return () => this._destroyCharts();
        });
    }

    _iso(d) {
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, "0");
        const day = String(d.getDate()).padStart(2, "0");
        return `${y}-${m}-${day}`;
    }

    async _loadChartJs() {
        try {
            await loadBundle("web.chartjs_lib");
        } catch (e) {
            await loadJS("/web/static/lib/Chart/Chart.js");
        }
    }

    async fetch_dropdowns() {
        try {
            // Use the existing location hierarchy method from pos.order
            const hierarchy = await this.orm.call('pos.order', 'get_location_hierarchy', []);
            this.state.provinces = hierarchy.provinces || [];
            this.state.cities = hierarchy.cities || [];
            this.state.zones = hierarchy.zones || [];
            this.state.segments_l1 = hierarchy.segments_l1 || [];
            this.state.segments_l2 = hierarchy.segments_l2 || [];
            this.state.segments_l3 = hierarchy.segments_l3 || [];
            this.state.segments_l4 = hierarchy.segments_l4 || [];
        } catch (err) {
            console.error("Failed to load location hierarchy:", err);
        }
    }

    get filteredCities() {
        if (!this.state.province_id) return this.state.cities;
        const pId = parseInt(this.state.province_id, 10);
        return this.state.cities.filter(c => c.province_id === pId);
    }

    get filteredZones() {
        if (!this.state.city_id) return this.state.zones;
        const cId = parseInt(this.state.city_id, 10);
        return this.state.zones.filter(z => z.city_id === cId);
    }

    get filteredSegmentsL2() {
        if (!this.state.segment_l1) return [];
        const pId = parseInt(this.state.segment_l1, 10);
        return this.state.segments_l2.filter(s => s.parent_id === pId);
    }

    get filteredSegmentsL3() {
        if (!this.state.segment_l2) return [];
        const pId = parseInt(this.state.segment_l2, 10);
        return this.state.segments_l3.filter(s => s.parent_id === pId);
    }

    get filteredSegmentsL4() {
        if (!this.state.segment_l3) return [];
        const pId = parseInt(this.state.segment_l3, 10);
        return this.state.segments_l4.filter(s => s.parent_id === pId);
    }

    async loadData() {
        this.state.loading = true;
        try {
            let effective_segment_id = null;
            if (this.state.segment_l4) effective_segment_id = parseInt(this.state.segment_l4, 10);
            else if (this.state.segment_l3) effective_segment_id = parseInt(this.state.segment_l3, 10);
            else if (this.state.segment_l2) effective_segment_id = parseInt(this.state.segment_l2, 10);
            else if (this.state.segment_l1) effective_segment_id = parseInt(this.state.segment_l1, 10);

            this.state.data = await this.orm.call(
                "livestock.dashboard",
                "get_dashboard_data",
                [
                    this.state.date_from || false, 
                    this.state.date_to || false, 
                    this.state.department || false,
                    this.state.province_id ? parseInt(this.state.province_id, 10) : false,
                    this.state.city_id ? parseInt(this.state.city_id, 10) : false,
                    this.state.zone_id ? parseInt(this.state.zone_id, 10) : false,
                    effective_segment_id || false,
                    this.state.segment_type || false
                ]
            );
        } catch (err) {
            console.error("[Livestock Dashboard] failed:", err);
            this.state.data = null;
        } finally {
            this.state.loading = false;
        }
    }

    async applyFilter(ev) {
        if (ev.target.name === "date_from") this.state.date_from = ev.target.value;
        else if (ev.target.name === "date_to") this.state.date_to = ev.target.value;
        else if (ev.target.name === "department") this.state.department = ev.target.value;
        else if (ev.target.name === "segment_l4") this.state.segment_l4 = ev.target.value;
        
        this.state.active_preset = null;
        await this.loadData();
    }

    async onchange_province() {
        this.state.city_id = null;
        this.state.zone_id = null;
        await this.loadData();
    }

    async onchange_city() {
        this.state.zone_id = null;
        await this.loadData();
    }

    async onchange_zone() {
        await this.loadData();
    }

    async onchange_segment_l1() {
        this.state.segment_l2 = null;
        this.state.segment_l3 = null;
        this.state.segment_l4 = null;
        await this.loadData();
    }

    async onchange_segment_l2() {
        this.state.segment_l3 = null;
        this.state.segment_l4 = null;
        await this.loadData();
    }

    async onchange_segment_l3() {
        this.state.segment_l4 = null;
        await this.loadData();
    }

    async applyPreset(ev) {
        const preset = ev.currentTarget.dataset.preset;
        const t = new Date();
        let from, to;
        switch (preset) {
            case "this_month":
                from = new Date(t.getFullYear(), t.getMonth(), 1);
                to = t; break;
            case "last_month":
                from = new Date(t.getFullYear(), t.getMonth() - 1, 1);
                to = new Date(t.getFullYear(), t.getMonth(), 0); break;
            case "this_quarter": {
                const q = Math.floor(t.getMonth() / 3);
                from = new Date(t.getFullYear(), q * 3, 1);
                to = t; break;
            }
            case "ytd":
                from = new Date(t.getFullYear(), 0, 1);
                to = t; break;
            case "all_time":
                from = null; to = null; break;
            default:
                return;
        }
        this.state.date_from = from ? this._iso(from) : "";
        this.state.date_to = to ? this._iso(to) : "";
        this.state.active_preset = preset;
        await this.loadData();
    }

    refresh() { return this.loadData(); }
    print() { window.print(); }

    openRecord(recordId) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "livestock.slaugther",
            res_id: recordId,
            view_mode: "form",
            target: "current",
        });
    }

    openStateList(stateKey) {
        const stateLabels = {
            'not_received': 'Draft',
            'slaughtered': 'Slaughtered',
            'cutting': 'Cutting',
            'material_request': 'Material Request',
            'done': 'Done',
        };
        const label = stateLabels[stateKey] || 'Livestock';
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: `${label} Slaughters`,
            res_model: "livestock.slaugther",
            view_mode: "tree,form",
            domain: [["state", "=", stateKey]],
            target: "current",
        });
    }

    formatCurrency(v) {
        if (v === undefined || v === null) return "0.00";
        return new Intl.NumberFormat("en-US", {
            minimumFractionDigits: 2, maximumFractionDigits: 2,
        }).format(v);
    }

    stateBadgeClass(key) {
        return {
            not_received: "text-bg-secondary",
            slaughtered: "text-bg-info",
            cutting: "text-bg-warning",
            material_request: "text-bg-primary",
            done: "text-bg-success",
        }[key] || "text-bg-secondary";
    }

    deptBadgeClass(name) {
        return {
            Meat: "text-bg-danger",
            Goat: "text-bg-success",
            Chicken: "text-bg-warning",
            Other: "text-bg-secondary",
        }[name] || "text-bg-secondary";
    }

    _destroyCharts() {
        Object.values(this.charts).forEach((c) => { try { c && c.destroy(); } catch (e) {} });
        this.charts = {};
    }

    renderCharts() {
        this._destroyCharts();
        const d = this.state.data;
        if (!d) return;

        // ---------- Trend (bar + line) ----------
        if (this.trendRef.el) {
            this.charts.trend = new Chart(this.trendRef.el, {
                type: "bar",
                data: {
                    labels: d.trend.map((t) => t.label),
                    datasets: [
                        {
                            type: "bar",
                            label: "Total",
                            data: d.trend.map((t) => t.total),
                            backgroundColor: "#0d6efd",
                            borderRadius: 4,
                        },
                        {
                            type: "line",
                            label: "Completed",
                            data: d.trend.map((t) => t.done),
                            borderColor: "#28a745",
                            backgroundColor: "#28a745",
                            borderWidth: 3,
                            tension: 0.3,
                            pointRadius: 4,
                            fill: false,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: "index", intersect: false },
                    plugins: { legend: { position: "top" } },
                    scales: {
                        x: { grid: { display: false } },
                        y: { beginAtZero: true, title: { display: true, text: "Animals" } },
                    },
                },
            });
        }

        // ---------- Department doughnut ----------
        if (this.deptRef.el) {
            const items = d.department_chart.filter((x) => x.count > 0);
            this.charts.dept = new Chart(this.deptRef.el, {
                type: "doughnut",
                data: {
                    labels: items.map((x) => x.label),
                    datasets: [{
                        data: items.map((x) => x.count),
                        backgroundColor: items.map((x) => x.color),
                        borderWidth: 1,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: "70%",
                    plugins: { legend: { position: "right" } },
                },
            });
        }

        // ---------- State pipeline (horizontal bar) ----------
        if (this.stateRef.el) {
            this.charts.state = new Chart(this.stateRef.el, {
                type: "bar",
                data: {
                    labels: d.state_chart.map((s) => s.label),
                    datasets: [{
                        data: d.state_chart.map((s) => s.count),
                        backgroundColor: d.state_chart.map((s) => s.color),
                        borderRadius: 4,
                    }],
                },
                options: {
                    indexAxis: "y",
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    onClick: (event, elements) => {
                        if (elements.length > 0) {
                            const index = elements[0].index;
                            const stateKey = d.state_chart[index].key;
                            this.openStateList(stateKey);
                        }
                    },
                    onHover: (event, elements) => {
                        event.native.target.style.cursor = elements.length ? 'pointer' : 'default';
                    },
                    scales: {
                        x: { beginAtZero: true, ticks: { precision: 0 } },
                        y: { grid: { display: false } },
                    },
                },
            });
        }

        // ---------- Source doughnut ----------
        if (this.sourceRef.el) {
            const items = d.source_chart.filter((x) => x.count > 0);
            this.charts.source = new Chart(this.sourceRef.el, {
                type: "doughnut",
                data: {
                    labels: items.map((x) => x.label),
                    datasets: [{
                        data: items.map((x) => x.count),
                        backgroundColor: items.map((x) => x.color),
                        borderWidth: 1,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: "70%",
                    plugins: { legend: { position: "right" } },
                },
            });
        }
    }
}

LivestockDashboard.template = "bn_livestock_slaugther.LivestockDashboardTemplate";
registry.category("actions").add("livestock_dashboard", LivestockDashboard);