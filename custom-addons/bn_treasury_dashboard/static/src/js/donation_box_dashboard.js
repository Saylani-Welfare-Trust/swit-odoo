/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, onWillStart, onMounted, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class DonationBoxDashboard extends Component {
    setup() {
        this.orm = useService('orm');
        this.actionService = useService("action");

        this.state = useState({
            date_from: '',
            date_to: '',
            province_id: null,
            city_id: null,
            zone_id: null,
            branch_id: null,
            provinces: [],
            cities: [],
            zones: [],
            branches: [],
            kpi: {
                available: 0, installed: 0, closed: 0,
                active_complaints: 0, resolved_complaints: 0, not_recovered: 0,
                total_collection: '0.00' // <-- NEW
            },
            chart_comp_status: { labels: [], data: [] },
            chart_installs: { labels: [], data: [] },
            recent_complaints: [],
            recent_registrations: [],
        });

        this._charts = {};
        this.is_mounted = false;

        onWillStart(async () => {
            await this.fetch_dropdowns();
            await this.fetch_data();
        });

        onMounted(() => {
            this.is_mounted = true;
            this.render_charts();
        });
    }

    async fetch_dropdowns() {
        const hierarchy = await this.orm.call('donation.box.dashboard', 'get_location_hierarchy', []);
        this.state.provinces = hierarchy.provinces || [];
        this.state.cities = hierarchy.cities || [];
        this.state.zones = hierarchy.zones || [];
        this.state.branches = hierarchy.branches || [];
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

    get filteredBranches() {
        if (!this.state.zone_id) return this.state.branches;
        const zId = parseInt(this.state.zone_id, 10);
        return this.state.branches.filter(b => b.zone_id === zId);
    }

    async fetch_data() {
        const data = await this.orm.call('donation.box.dashboard', 'get_dashboard_data', [
            this.state.date_from || null,
            this.state.date_to || null,
            this.state.province_id ? parseInt(this.state.province_id, 10) : null,
            this.state.city_id ? parseInt(this.state.city_id, 10) : null,
            this.state.zone_id ? parseInt(this.state.zone_id, 10) : null,
            this.state.branch_id ? parseInt(this.state.branch_id, 10) : null,
        ]);
        
        this.state.kpi = data.kpi;
        this.state.chart_comp_status = data.chart_comp_status;
        this.state.chart_installs = data.chart_installs;
        this.state.recent_complaints = data.recent_complaints;
        this.state.recent_registrations = data.recent_registrations;

        if (this.is_mounted) {
            this.render_charts();
        }
    }

    async applyFilter() {
        await this.fetch_data();
    }

    async onchange_province() {
        this.state.city_id = null;
        this.state.zone_id = null;
        this.state.branch_id = null;
        await this.applyFilter();
    }

    async onchange_city() {
        this.state.zone_id = null;
        this.state.branch_id = null;
        await this.applyFilter();
    }
    
    async onchange_zone() {
        this.state.branch_id = null;
        await this.applyFilter();
    }

    clearFilter() {
        this.state.date_from = '';
        this.state.date_to = '';
        this.state.province_id = null;
        this.state.city_id = null;
        this.state.zone_id = null;
        this.state.branch_id = null;
        this.applyFilter();
    }

    setQuickDate(type) {
        const today = new Date();
        const yyyy = today.getFullYear();
        const month = today.getMonth();

        const fmt = (d) => {
            const y = d.getFullYear();
            const m = String(d.getMonth() + 1).padStart(2, '0');
            const dd = String(d.getDate()).padStart(2, '0');
            return `${y}-${m}-${dd}`;
        };

        if (type === 'this_month') {
            this.state.date_from = fmt(new Date(yyyy, month, 1));
            this.state.date_to = fmt(new Date(yyyy, month + 1, 0));
        } else if (type === 'last_month') {
            this.state.date_from = fmt(new Date(yyyy, month - 1, 1));
            this.state.date_to = fmt(new Date(yyyy, month, 0));
        } else if (type === 'this_year') {
            this.state.date_from = `${yyyy}-01-01`;
            this.state.date_to = `${yyyy}-12-31`;
        }
        this.applyFilter();
    }

    render_charts() {
        const ctx1 = $("#db_chart_complaints");
        if (ctx1.length) {
            if (this._charts.comp_status) this._charts.comp_status.destroy();
            this._charts.comp_status = new Chart(ctx1, {
                type: 'doughnut',
                data: {
                    labels: this.state.chart_comp_status.labels,
                    datasets: [{
                        data: this.state.chart_comp_status.data,
                        backgroundColor: ["#ff6384", "#36a2eb", "#cc65fe", "#ffce56", "#4bc0c0"],
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right' } } }
            });
        }

        const ctx2 = $("#db_chart_installs");
        if (ctx2.length) {
            if (this._charts.installs) this._charts.installs.destroy();
            this._charts.installs = new Chart(ctx2, {
                type: 'bar',
                data: {
                    labels: this.state.chart_installs.labels,
                    datasets: [{
                        label: 'Installations',
                        data: this.state.chart_installs.data,
                        backgroundColor: "rgba(75, 192, 192, 0.8)",
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }
    }

    formatStateName(stateName) {
        if (!stateName) return '';
        return stateName.charAt(0).toUpperCase() + stateName.slice(1).replace(/_/g, ' ');
    }

    getStateColor(stateName) {
        if (!stateName) return 'bg-secondary';
        const s = stateName.toLowerCase();
        if (['available', 'resolved', 'repaired'].includes(s)) return 'bg-success';
        if (['installed', 'process'].includes(s)) return 'bg-info';
        if (['missing', 'robbery', 'not_recovered', 'broken'].includes(s)) return 'bg-danger';
        return 'bg-warning text-dark';
    }
    
    openView(model, domain = []) {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: model,
            views: [[false, 'list'], [false, 'form']],
            domain: domain,
            target: 'current'
        });
    }
}

DonationBoxDashboard.template = 'DonationBoxDashboard';
registry.category("actions").add("donation_box_dashboard", DonationBoxDashboard);