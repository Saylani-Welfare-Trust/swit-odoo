/** @odoo-module **/
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";


export class PosDashboard extends Component {
    setup() {
        super.setup(...arguments);
        this.orm = useService('orm');
        this.user = useService("user");
        this.actionService = useService("action");
        this.notification = useService("notification");

        const savedState = this.loadSavedState();
        
        this.state = useState({
            payment_details: [],
            top_salesperson: [],
            selling_product: [],
            total_sale: [],
            total_order_count: [],
            total_refund_count: [],
            total_session: [],
            today_refund_total: [],
            today_sale: [],
            sales_target: {
                target_amount: 0,
                current_amount: 0,
                achievement_percentage: 0,
                period: 'Current Month'
            },
            peak_hours: [],
            top_customers_detailed: [],

            current_filter: savedState.current_filter || 'today',
            current_chart_type: savedState.current_chart_type || 'bar',
            date_range: savedState.date_range || 'today',
            start_date: savedState.start_date || this.formatDate(new Date()),
            end_date: savedState.end_date || this.formatDate(new Date()),
            current_filter: 'today',
            current_chart_type: 'bar',
            
            // New state for profit margin
            profit_margin_data: [],
            profit_summary: {
                total_revenue_display: 'PKR 0.00',
                total_cost_display: 'PKR 0.00',
                total_profit_display: 'PKR 0.00',
                overall_margin_percentage_display: '0%',
                total_orders: 0,
                avg_profit_per_order_display: 'PKR 0.00'
            },
            profit_trend_data: null,
            top_profitable_categories: [],
            profit_chart_type: 'doughnut',
            profit_chart_title: 'Profit Distribution',
            peak_hours_chart_type: 'curve',
            peak_hours_title: 'Peak Sales Hours (Curve)',
            date_range: 'today',
            start_date: this.formatDate(new Date()),
            end_date: this.formatDate(new Date()),
            top_products_data: [[], []],
            top_categories_data: [[], []],

            expense_revenue_data: {
                total_revenue: 0, total_expense: 0, total_profit: 0, profit_margin: 0,
                total_revenue_display: 'PKR 0.00',
                total_expense_display: 'PKR 0.00',
                total_profit_display: 'PKR 0.00',
                profit_margin_display: '0%',
                year: new Date().getFullYear(),
                month: null,
                period: 'Current Year'
            },
            expense_revenue_monthly: {
                year: new Date().getFullYear(),
                months: [],
                summary: {
                    total_revenue_display: 'PKR 0',
                    total_expense_display: 'PKR 0',
                    total_profit_display: 'PKR 0',
                    avg_margin_display: '0%'
                }
            },
            expense_revenue_yearly: {
                years: [],
                current_year: new Date().getFullYear()
            },
            available_years: [],
            selected_month: null,
            selected_year: new Date().getFullYear(),
            expense_chart_type: 'bar', 


            
        });
        
        this.change_expense_chart_type = (type) => {
            console.log('Changing expense chart type to:', type);
            this.state.expense_chart_type = type;
            this.render_expense_revenue_chart();
            this.show_notification(`Chart type changed to ${type}`, 'info');
        };

        this.change_expense_year = async (year) => {
            this.state.selected_year = year;
            this.state.selected_month = null; // Reset month when changing year
            
            await this.fetch_expense_revenue_data();
            await this.render_expense_revenue_chart();
            
            this.show_notification(`Year changed to ${year}`, 'info');
        };

        this.change_expense_month = async (month) => {
            this.state.selected_month = month;
            
            await this.fetch_expense_revenue_data();
            await this.render_expense_revenue_chart();
            
            const monthNames = [
                'January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December'
            ];
            
            this.show_notification(`Month changed to ${monthNames[month-1]}`, 'info');
        };

        // Chart instances
        this.charts = {
            sales: null,
            target: null,
            products: null,
            categories: null,
            hours: null,
            profit_trend: null,
            profit_margin: null
        };
        
        onWillStart(async () => {
            await this.fetch_data_with_filter();
            await this.fetch_expense_revenue_data();  // Add this line
            await this.fetch_available_years();       // Add this line
            await this.render_all_charts();
        });
        
        onMounted(async () => {
            await this.render_all_charts();
            this.setup_event_listeners();
            this.setup_date_pickers(); 
            this.animate_elements();
            this.saveState()
        });
    }

    // Add reset method to clear saved state
        // Add reset method to clear saved state
    reset_to_default() {
        if (confirm('Reset dashboard to default settings? This will clear all saved filters.')) {
            try {
                // Clear saved state
                localStorage.removeItem('pos_dashboard_state');
                
                // Reset to default values
                this.state.current_filter = 'today';
                this.state.current_chart_type = 'bar';
                this.state.date_range = 'today';
                this.state.start_date = this.formatDate(new Date());
                this.state.end_date = this.formatDate(new Date());
                this.state.profit_chart_type = 'doughnut';
                this.state.peak_hours_chart_type = 'curve';
                
                // REMOVE THESE LINES - They're redefining methods incorrectly
                // this.change_expense_chart_type = (type) => {
                //     console.log('Changing expense chart type to:', type);
                //     this.state.expense_chart_type = type;
                //     this.render_expense_revenue_chart();
                //     this.show_notification(`Chart type changed to ${type}`, 'info');
                // };

                // this.change_expense_year = async (year) => {
                //     this.state.selected_year = year;
                //     this.state.selected_month = null; // Reset month when changing year
                    
                //     await this.fetch_expense_revenue_data();
                //     await this.render_expense_revenue_chart();
                    
                //     this.show_notification(`Year changed to ${year}`, 'info');
                // };

                // this.change_expense_month = async (month) => {
                //     this.state.selected_month = month;
                    
                //     await this.fetch_expense_revenue_data();
                //     await this.render_expense_revenue_chart();
                    
                //     const monthNames = [
                //         'January', 'February', 'March', 'April', 'May', 'June',
                //         'July', 'August', 'September', 'October', 'November', 'December'
                //     ];
                    
                //     this.show_notification(`Month changed to ${monthNames[month-1]}`, 'info');
                // };
                
                // Update UI elements
                const dateRangeSelect = document.getElementById('date_range');
                if (dateRangeSelect) {
                    dateRangeSelect.value = 'today';
                }
                
                this.toggle_date_pickers();
                
                // Refresh with default values
                this.refresh_data_with_filter();
                
                this.show_notification('Dashboard reset to default settings', 'success');
            } catch (error) {
                console.error('Error resetting dashboard:', error);
                this.show_notification('Error resetting dashboard', 'danger');
            }
        }
    }

    loadSavedState() {
        try {
            const saved = localStorage.getItem('pos_dashboard_state');
            if (saved) {
                return JSON.parse(saved);
            }
        } catch (e) {
            console.warn('Failed to load saved state:', e);
        }
        return {};
    }

     // Save current state to localStorage
    saveState() {
        try {
            const stateToSave = {
                current_filter: this.state.current_filter,
                current_chart_type: this.state.current_chart_type,
                date_range: this.state.date_range,
                start_date: this.state.start_date,
                end_date: this.state.end_date,
                profit_chart_type: this.state.profit_chart_type,
                peak_hours_chart_type: this.state.peak_hours_chart_type
            };
            localStorage.setItem('pos_dashboard_state', JSON.stringify(stateToSave));
        } catch (e) {
            console.warn('Failed to save state:', e);
        }
    }

    _get_sample_profit_data() {
        return [
            {
                product_id: null,
                product_name: 'No sales recorded',
                total_quantity: 0,
                total_revenue_display: '—',
                total_cost_display: '—',
                total_profit_display: '—',
                profit_margin_percentage: 0,
                profit_margin_percentage_display: '0%',
                margin_status: 'none',
                margin_status_label: 'No Data'
            }
        ];
    }

    _get_default_profit_summary() {
        return {
            total_revenue_display: 'GH¢0.00',
            total_cost_display: 'GH¢0.00',
            total_profit_display: 'GH¢0.00',
            overall_margin_percentage_display: '0%',
            total_orders: 0,
            avg_profit_per_order_display: 'GH¢0.00'
        };
    }

    _get_default_profit_trend_data() {
        return {
            labels: ['No Data'],
            datasets: [{
                label: 'Profit',
                data: [0],
                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                borderColor: 'rgba(75, 192, 192, 1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4
            }],
            type: 'line',
            x_axis_label: 'No Data Available',
            total_profit: 0,
            total_revenue: 0,
            total_cost: 0
        };
    }
    // Helper method to extract name from translation object
    extractTranslatedName(nameObj) {
        if (!nameObj) return 'Unknown';
        
        // If it's already a string, return it
        if (typeof nameObj === 'string') {
            // Check if it's a JSON string
            if (nameObj.startsWith('{') && nameObj.endsWith('}')) {
                try {
                    const parsed = JSON.parse(nameObj);
                    // Return the first value in the object (usually contains translation)
                    const keys = Object.keys(parsed);
                    if (keys.length > 0) {
                        return parsed[keys[0]];
                    }
                } catch (e) {
                    console.warn('Failed to parse name JSON:', e);
                }
            }
            return nameObj;
        }
        
        // If it's an object, extract the value
        if (typeof nameObj === 'object' && nameObj !== null) {
            // Try to get the name from common fields
            if (nameObj.product_name) return this.extractTranslatedName(nameObj.product_name);
            if (nameObj.name) return this.extractTranslatedName(nameObj.name);
            if (nameObj.product_category) return this.extractTranslatedName(nameObj.product_category);
            if (nameObj.category_name) return this.extractTranslatedName(nameObj.category_name);
            
            // Try to get first property value
            const keys = Object.keys(nameObj);
            if (keys.length > 0) {
                return this.extractTranslatedName(nameObj[keys[0]]);
            }
        }
        
        return 'Unknown';
    }

    // MOVE ALL ARROW FUNCTIONS HERE (outside setup method)
    formatDate(date) {
        const d = new Date(date);
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }

    getDateRange() {
        const today = new Date();
        let start_date, end_date;
        
        switch(this.state.date_range) {
            case 'today':
                start_date = today;
                end_date = today;
                break;
            case 'yesterday':
                const yesterday = new Date(today);
                yesterday.setDate(yesterday.getDate() - 1);
                start_date = yesterday;
                end_date = yesterday;
                break;
            case 'last_week':
                start_date = new Date(today);
                start_date.setDate(start_date.getDate() - 7);
                end_date = today;
                break;
            case 'last_month':
                start_date = new Date(today);
                start_date.setDate(start_date.getDate() - 30);
                end_date = today;
                break;
            case 'last_year':
                start_date = new Date(today);
                start_date.setDate(start_date.getDate() - 365);
                end_date = today;
                break;
            case 'this_month':
                start_date = new Date(today.getFullYear(), today.getMonth(), 1);
                end_date = today;
                break;
            case 'last_month_complete':
                const firstDayLastMonth = new Date(today.getFullYear(), today.getMonth() - 1, 1);
                const lastDayLastMonth = new Date(today.getFullYear(), today.getMonth(), 0);
                start_date = firstDayLastMonth;
                end_date = lastDayLastMonth;
                break;
            case 'this_year':
                start_date = new Date(today.getFullYear(), 0, 1);
                end_date = today;
                break;
            case 'last_year_complete':
                start_date = new Date(today.getFullYear() - 1, 0, 1);
                end_date = new Date(today.getFullYear() - 1, 11, 31);
                break;
            case 'custom':
                // Use the date picker values
                start_date = new Date(this.state.start_date);
                end_date = new Date(this.state.end_date);
                break;
            default:
                start_date = today;
                end_date = today;
        }
        
        return {
            start_date: this.formatDate(start_date),
            end_date: this.formatDate(end_date)
        };
    }

    setup_date_pickers() {
        const dateRangeSelect = document.getElementById('date_range');
        const startDateContainer = document.getElementById('start_date_container');
        const endDateContainer = document.getElementById('end_date_container');
        const startDateInput = document.getElementById('start_date');
        const endDateInput = document.getElementById('end_date');
        
        if (dateRangeSelect) {
            dateRangeSelect.value = this.state.date_range;
            dateRangeSelect.addEventListener('change', (e) => this.on_date_range_change(e));
        }
        
        // Set initial dates from state
        if (startDateInput) {
            startDateInput.value = this.state.start_date;
            startDateInput.addEventListener('change', (e) => {
                this.state.start_date = e.target.value;
                this.saveState(); // Save when date changes
                if (this.state.date_range === 'custom') {
                    this.refresh_data_with_filter();
                }
            });
        }
        
        if (endDateInput) {
            endDateInput.value = this.state.end_date;
            endDateInput.addEventListener('change', (e) => {
                this.state.end_date = e.target.value;
                this.saveState(); // Save when date changes
                if (this.state.date_range === 'custom') {
                    this.refresh_data_with_filter();
                }
            });
        }
        
        // Show/hide date pickers based on selection
        this.toggle_date_pickers();
    }

    toggle_date_pickers() {
        const startDateContainer = document.getElementById('start_date_container');
        const endDateContainer = document.getElementById('end_date_container');
        
        if (startDateContainer && endDateContainer) {
            if (this.state.date_range === 'custom') {
                startDateContainer.style.display = 'block';
                endDateContainer.style.display = 'block';
            } else {
                startDateContainer.style.display = 'none';
                endDateContainer.style.display = 'none';
            }
        }
    }

    on_date_range_change(event) {
        const value = event.target.value;
        this.state.date_range = value;
        
        // Update dates based on selection
        if (value !== 'custom') {
            const dateRange = this.getDateRange();
            this.state.start_date = dateRange.start_date;
            this.state.end_date = dateRange.end_date;
        }
        
        this.toggle_date_pickers();
        
        // Save state immediately
        this.saveState();
        
        // Then refresh data
        this.refresh_data_with_filter();
    }
    
    // Method to change peak hours chart type
    changePeakHoursChartType = (type) => {
        console.log('Changing peak hours chart type to:', type);
        this.state.peak_hours_chart_type = type;
        this.updatePeakHoursTitle(type);
        
        // Save state
        this.saveState();
        
        this.render_hours_chart();
    };

    // Method to update peak hours chart title
    updatePeakHoursTitle = (type) => {
        const titles = {
            'curve': 'Peak Sales Hours (Curve)',
            'line': 'Peak Sales Hours (Line)',
            'bar': 'Peak Sales Hours (Bar Chart)'
        };
        this.state.peak_hours_title = titles[type] || titles.curve;
    };

    // Method to get peak hour info
    getPeakHourInfo = () => {
        const hoursData = this.state.peak_hours_data?.all_hours || [];
        if (hoursData.length === 0) {
            return { hour: 'N/A', sales: 0, orders: 0 };
        }
        
        // Find the hour with maximum sales
        const peak = hoursData.reduce((max, hour) => {
            return hour.total_amount > max.total_amount ? hour : max;
        }, hoursData[0]);
        
        return {
            hour: peak.hour_display || 'N/A',
            period: peak.period || '',
            sales: peak.total_amount || 0,
            orders: peak.order_count || 0
        };
    };


    // Method to get insight about peak hours
    getPeakHoursInsight() {
        const hoursData = this.state.peak_hours_data?.all_hours || [];
        if (hoursData.length === 0) return 'No data available';
        
        const peak = this.getPeakHourInfo();
        const periods = this.state.peak_hours_data?.time_periods || [];
        
        if (periods.length > 0) {
            const topPeriod = periods[0];
            return `Peak sales at ${peak.hour} (${peak.period}). Top period: ${topPeriod.period} with PKR ${topPeriod.total_amount.toFixed(2)}`;
        } else {
            return `Peak sales at ${peak.hour} with PKR ${peak.sales.toFixed(2)}`;
        }
    }
    getBusiestPeriod = () => {
        const periods = this.state.peak_hours_data?.time_periods || [];
        if (periods.length === 0) {
            return { period: 'N/A', sales: 0, orders: 0 };
        }
        
        return {
            period: periods[0].period || 'N/A',
            sales: periods[0].total_amount || 0,
            orders: periods[0].order_count || 0
        };
    };

    // Profit chart methods
    changeProfitChartType = (type) => {
        console.log('Changing profit chart type to:', type);
        this.state.profit_chart_type = type;
        this.updateProfitChartTitle(type);
        
        // Save state
        this.saveState();
        
        this.render_profit_margin_chart();
    };

    updateProfitChartTitle = (type) => {
        const titles = {
            'doughnut': 'Profit Distribution (Donut Chart)',
            'pie': 'Profit Distribution (Pie Chart)',
            'bar': 'Top Products by Profit Margin (Bar Chart)'
        };
        this.state.profit_chart_title = titles[type] || titles.doughnut;
    };

    // Also update the template calls - Remove arrow functions from template
    // Change from: t-on-click="() => changeProfitChartType('doughnut')"
    // To: t-on-click="changeProfitChartTypeDoughnut"
    
    changeProfitChartTypeDoughnut = () => {
        this.changeProfitChartType('doughnut');
    };
    
    changeProfitChartTypePie = () => {
        this.changeProfitChartType('pie');
    };
    
    changeProfitChartTypeBar = () => {
        this.changeProfitChartType('bar');
    };
    
    changePeakHoursChartTypeCurve = () => {
        this.changePeakHoursChartType('curve');
    };
    
    changePeakHoursChartTypeLine = () => {
        this.changePeakHoursChartType('line');
    };
    
    changePeakHoursChartTypeBar = () => {
        this.changePeakHoursChartType('bar');
    };

    animate_elements() {
        // Add animation classes to elements
        const elements = document.querySelectorAll('.scale-in, .slide-up, .slide-down, .slide-left, .slide-right');
        elements.forEach((el, index) => {
            setTimeout(() => {
                el.style.opacity = '1';
                el.style.transform = 'translate(0, 0) scale(1)';
            }, index * 100);
        });
    }

    renderEmptyChart(ctx, message) {
        this.charts.profit_trend = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [message],
                datasets: [{
                    label: 'No Data',
                    data: [0],
                    backgroundColor: 'rgba(220, 220, 220, 0.1)',
                    borderColor: 'rgba(220, 220, 220, 1)',
                    borderWidth: 1,
                    pointRadius: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    title: {
                        display: true,
                        text: message,
                        font: {
                            size: 14
                        },
                        color: '#888'
                    },
                    tooltip: {
                        enabled: false
                    }
                },
                scales: {
                    y: {
                        display: false
                    },
                    x: {
                        display: false
                    }
                }
            }
        });
    }
    async refresh_data_with_filter() {
        this.show_notification('Applying filter...', 'info');
        
        // Update current filter based on date range
        if (this.state.date_range !== 'custom') {
            this.state.current_filter = this.state.date_range;
        }
        
        await this.fetch_data_with_filter();
        await this.render_all_charts();
        
        // Save state after applying filter
        this.saveState();
        
        this.show_notification('Filter applied successfully!', 'success');
    }

    async fetch_top_products_and_categories() {
        try {
            console.log('Fetching top products and categories for filter:', this.state.date_range);
            
            const dateRange = this.getDateRange();
            
            if (this.state.date_range === 'custom') {
                const topProducts = await this.orm.call('pos.order', 'get_top_products_with_dates', [
                    dateRange.start_date, 
                    dateRange.end_date
                ]);
                console.log('Raw top products data (custom):', topProducts);
                this.state.top_products_data = topProducts || [[], []];
                
                const topCategories = await this.orm.call('pos.order', 'get_top_categories_with_dates', [
                    dateRange.start_date, 
                    dateRange.end_date
                ]);
                console.log('Raw top categories data (custom):', topCategories);
                this.state.top_categories_data = topCategories || [[], []];
            } else {
                const topProducts = await this.orm.call('pos.order', 'get_the_top_products', [this.state.date_range]);
                console.log('Raw top products data (filter):', topProducts);
                this.state.top_products_data = topProducts || [[], []];
                
                const topCategories = await this.orm.call('pos.order', 'get_the_top_categories', [this.state.date_range]);
                console.log('Raw top categories data (filter):', topCategories);
                this.state.top_categories_data = topCategories || [[], []];
            }
            
        } catch (error) {
            console.error('Error fetching top products and categories:', error);
            this.state.top_products_data = [[], []];
            this.state.top_categories_data = [[], []];
        }
    }

    async fetch_expense_revenue_data() {
        try {
            console.log('Fetching expense vs revenue data...');
            
            // Fetch current year data
            const data = await this.orm.call('pos.order', 'get_expense_revenue_comparison', [
                this.state.selected_year,
                this.state.selected_month
            ]);
            
            this.state.expense_revenue_data = data || {
                total_revenue: 0,
                total_expense: 0,
                total_profit: 0,
                profit_margin: 0,
                total_revenue_display: 'GH¢ 0.00',
                total_expense_display: 'GH¢ 0.00',
                total_profit_display: 'GH¢ 0.00',
                profit_margin_display: '0%',
                year: this.state.selected_year,
                month: this.state.selected_month,
                period: 'No Data'
            };
            
            // Fetch monthly data for the selected year
            const monthlyData = await this.orm.call('pos.order', 'get_expense_revenue_monthly', [
                this.state.selected_year
            ]);
            
            this.state.expense_revenue_monthly = monthlyData || {
                year: this.state.selected_year,
                months: [],
                summary: {
                    total_revenue_display: 'GH¢ 0',
                    total_expense_display: 'GH¢ 0',
                    total_profit_display: 'GH¢ 0',
                    avg_margin_display: '0%'
                }
            };
            
            // Fetch yearly comparison
            const yearlyData = await this.orm.call('pos.order', 'get_expense_revenue_yearly', [5]);
            this.state.expense_revenue_yearly = yearlyData || {
                years: [],
                current_year: this.state.selected_year
            };
            
            console.log('Expense vs revenue data loaded:', {
                current: this.state.expense_revenue_data,
                monthly_count: this.state.expense_revenue_monthly.months.length,
                yearly_count: this.state.expense_revenue_yearly.years.length
            });
            
        } catch (error) {
            console.error('Error fetching expense vs revenue data:', error);
            this.show_notification('Error loading expense vs revenue data', 'danger');
        }
    }

    async fetch_available_years() {
        try {
            const years = await this.orm.call('pos.order', 'get_available_years', []);
            this.state.available_years = years || [new Date().getFullYear()];
            
            // Set default selected year to current year if available
            const currentYear = new Date().getFullYear();
            if (!this.state.available_years.includes(currentYear)) {
                this.state.available_years.unshift(currentYear);
            }
            
        } catch (error) {
            console.error('Error fetching available years:', error);
            this.state.available_years = [new Date().getFullYear()];
        }
    }

    async change_expense_year(year) {
        this.state.selected_year = year;
        this.state.selected_month = null; // Reset month when changing year
        
        await this.fetch_expense_revenue_data();
        await this.render_expense_revenue_chart();
        
        this.show_notification(`Year changed to ${year}`, 'info');
    }

    async change_expense_month(month) {
        this.state.selected_month = month;
        
        await this.fetch_expense_revenue_data();
        await this.render_expense_revenue_chart();
        
        const monthNames = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ];
        
        this.show_notification(`Month changed to ${monthNames[month-1]}`, 'info');
    }

    change_expense_chart_type(type) {
        this.state.expense_chart_type = type;
        this.render_expense_revenue_chart();
        this.show_notification(`Chart type changed to ${type}`, 'info');
    }

    async render_expense_revenue_chart() {
        const canvas = document.getElementById('expense_revenue_chart');
        if (!canvas) return;
        
        // Destroy existing chart
        if (this.charts.expense_revenue) {
            this.charts.expense_revenue.destroy();
        }
        
        const ctx = canvas.getContext('2d');
        const monthlyData = this.state.expense_revenue_monthly.months || [];
        
        if (monthlyData.length === 0) {
            this.renderEmptyChart(ctx, 'No data available');
            return;
        }
        
        const monthNames = monthlyData.map(m => m.month_name);
        const revenueData = monthlyData.map(m => m.revenue || 0);
        const expenseData = monthlyData.map(m => m.expense || 0);
        const profitData = monthlyData.map(m => m.profit || 0);
        
        const chartType = this.state.expense_chart_type || 'bar';
        
        if (chartType === 'stacked') {
            // Stacked bar chart
            this.charts.expense_revenue = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: monthNames,
                    datasets: [
                        {
                            label: 'Revenue',
                            data: revenueData,
                            backgroundColor: 'rgba(54, 162, 235, 0.8)',
                            borderColor: 'rgba(54, 162, 235, 1)',
                            borderWidth: 1
                        },
                        {
                            label: 'Expense',
                            data: expenseData,
                            backgroundColor: 'rgba(255, 99, 132, 0.8)',
                            borderColor: 'rgba(255, 99, 132, 1)',
                            borderWidth: 1
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                        },
                        title: {
                            display: true,
                            text: `Monthly Expense vs Revenue - ${this.state.selected_year}`,
                            font: {
                                size: 14,
                                weight: 'bold'
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    let label = context.dataset.label || '';
                                    if (label) {
                                        label += ': ';
                                    }
                                    if (context.parsed.y !== null) {
                                        return `${label}GH¢${context.parsed.y.toLocaleString()}`;
                                    }
                                    return label;
                                },
                                footer: function(tooltipItems) {
                                    if (tooltipItems.length === 2) {
                                        const revenue = tooltipItems[0].parsed.y;
                                        const expense = tooltipItems[1].parsed.y;
                                        const profit = revenue - expense;
                                        const margin = revenue > 0 ? (profit / revenue * 100).toFixed(1) : 0;
                                        return [
                                            `Profit: GH¢${profit.toLocaleString()}`,
                                            `Margin: ${margin}%`
                                        ];
                                    }
                                    return '';
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            stacked: true,
                            title: {
                                display: true,
                                text: 'Months'
                            }
                        },
                        y: {
                            stacked: true,
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Amount (GH¢)'
                            },
                            ticks: {
                                callback: function(value) {
                                    return 'GH¢' + value.toLocaleString();
                                }
                            }
                        }
                    }
                }
            });
        } else if (chartType === 'line') {
            // Line chart
            this.charts.expense_revenue = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: monthNames,
                    datasets: [
                        {
                            label: 'Revenue',
                            data: revenueData,
                            backgroundColor: 'rgba(54, 162, 235, 0.2)',
                            borderColor: 'rgba(54, 162, 235, 1)',
                            borderWidth: 3,
                            fill: true,
                            tension: 0.4
                        },
                        {
                            label: 'Expense',
                            data: expenseData,
                            backgroundColor: 'rgba(255, 99, 132, 0.2)',
                            borderColor: 'rgba(255, 99, 132, 1)',
                            borderWidth: 3,
                            fill: true,
                            tension: 0.4
                        },
                        {
                            label: 'Profit',
                            data: profitData,
                            backgroundColor: 'rgba(75, 192, 192, 0.2)',
                            borderColor: 'rgba(75, 192, 192, 1)',
                            borderWidth: 3,
                            fill: true,
                            tension: 0.4
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                        },
                        title: {
                            display: true,
                            text: `Monthly Trend - ${this.state.selected_year}`,
                            font: {
                                size: 14,
                                weight: 'bold'
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const label = context.dataset.label || '';
                                    return `${label}: GH¢${context.parsed.y.toLocaleString()}`;
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Amount (GH¢)'
                            },
                            ticks: {
                                callback: function(value) {
                                    return 'GH¢' + value.toLocaleString();
                                }
                            }
                        }
                    }
                }
            });
        } else {
            // Bar chart (default)
            this.charts.expense_revenue = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: monthNames,
                    datasets: [
                        {
                            label: 'Revenue',
                            data: revenueData,
                            backgroundColor: 'rgba(54, 162, 235, 0.7)',
                            borderColor: 'rgba(54, 162, 235, 1)',
                            borderWidth: 1
                        },
                        {
                            label: 'Expense',
                            data: expenseData,
                            backgroundColor: 'rgba(255, 99, 132, 0.7)',
                            borderColor: 'rgba(255, 99, 132, 1)',
                            borderWidth: 1
                        },
                        {
                            label: 'Profit',
                            data: profitData,
                            backgroundColor: 'rgba(75, 192, 192, 0.7)',
                            borderColor: 'rgba(75, 192, 192, 1)',
                            borderWidth: 1
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                        },
                        title: {
                            display: true,
                            text: `Monthly Expense vs Revenue - ${this.state.selected_year}`,
                            font: {
                                size: 14,
                                weight: 'bold'
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const label = context.dataset.label || '';
                                    return `${label}: GH¢${context.parsed.y.toLocaleString()}`;
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Amount (GH¢)'
                            },
                            ticks: {
                                callback: function(value) {
                                    return 'GH¢' + value.toLocaleString();
                                }
                            }
                        }
                    }
                }
            });
        }
    }

    async fetch_data_with_filter() {
        const dateRange = this.getDateRange();
        
        try {
            console.log('Fetching filtered data for range:', dateRange, 'date_range:', this.state.date_range);
            
            // Fetch refund details with date range
            const refundDetails = await this.orm.call('pos.order', 'get_refund_details_with_dates', [
                dateRange.start_date, 
                dateRange.end_date
            ]);
            
            this.state.total_sale = refundDetails['total_sale'] || '0';
            this.state.total_order_count = refundDetails['total_order_count'] || 0;
            this.state.total_refund_count = refundDetails['total_refund_count'] || 0;
            this.state.total_session = refundDetails['total_session'] || 0;
            this.state.today_refund_total = refundDetails['today_refund_total'] || 0;
            this.state.today_sale = refundDetails['today_sale'] || 0;
            
            // Fetch other data with date range
            const details = await this.orm.call('pos.order', 'get_details_with_dates', [
                dateRange.start_date, 
                dateRange.end_date
            ]);
            
            this.state.payment_details = details['payment_details'] || [];
            this.state.top_salesperson = details['salesperson'] || [];
            this.state.selling_product = details['selling_product'] || [];
            
            // Fetch additional data based on filter type
            if (this.state.date_range === 'custom') {
                await this.fetch_profit_data_with_dates(dateRange.start_date, dateRange.end_date);
                await this.fetch_additional_data_with_dates(dateRange.start_date, dateRange.end_date);
            } else {
                // Use the regular methods for predefined filters
                await this.fetch_profit_data();
                await this.fetch_additional_data();
            }
            
            // Always fetch top products and categories
            await this.fetch_top_products_and_categories();
            
        } catch (error) {
            console.error('Error fetching filtered data:', error);
            this.show_notification('Error loading filtered data', 'danger');
        }
    }
    
    async onWillStartActions() {
        // Don't fetch default data anymore - use filtered data
        await this.fetch_data_with_filter();
        await this.render_all_charts();
    }

    async fetch_profit_data_with_dates(start_date, end_date) {
        try {
            console.log('Fetching profit data for custom dates:', start_date, end_date);
            
            // Use the custom date methods with error handling
            let profitData = [];
            let profitSummary = {};
            let profitableCategories = [];
            let profitTrend = {};
            
            try {
                profitData = await this.orm.call('pos.order', 'get_profit_margin_analysis_with_dates', [
                    start_date, 
                    end_date
                ]);
            } catch (error) {
                console.error('Error fetching profit margin analysis:', error);
                profitData = this._get_sample_profit_data();
            }
            
            try {
                profitSummary = await this.orm.call('pos.order', 'get_profit_summary_with_dates', [
                    start_date, 
                    end_date
                ]);
            } catch (error) {
                console.error('Error fetching profit summary:', error);
                profitSummary = this._get_default_profit_summary();
            }
            
            try {
                profitableCategories = await this.orm.call('pos.order', 'get_top_profitable_categories_with_dates', [
                    5, 
                    start_date, 
                    end_date
                ]);
            } catch (error) {
                console.error('Error fetching profitable categories:', error);
                profitableCategories = [];
            }
            
            try {
                // FIXED: Use the new method for custom date range profit trend
                profitTrend = await this.orm.call('pos.order', 'get_profit_trend_analysis_with_dates', [
                    start_date, 
                    end_date
                ]);
            } catch (error) {
                console.error('Error fetching profit trend with custom dates:', error);
                profitTrend = this._get_default_profit_trend_data();
            }
            
            this.state.profit_margin_data = profitData || [];
            this.state.profit_summary = profitSummary || this._get_default_profit_summary();
            this.state.top_profitable_categories = profitableCategories || [];
            this.state.profit_trend_data = profitTrend || this._get_default_profit_trend_data();
            
            console.log('Profit data loaded for custom dates:', {
                margin_data_count: this.state.profit_margin_data.length,
                summary: this.state.profit_summary,
                categories_count: this.state.top_profitable_categories.length,
                trend_data: this.state.profit_trend_data
            });
            
        } catch (error) {
            console.error('General error in fetch_profit_data_with_dates:', error);
            
            // Fallback to sample data
            this.state.profit_margin_data = this._get_sample_profit_data();
            this.state.profit_summary = this._get_default_profit_summary();
            this.state.top_profitable_categories = [];
            this.state.profit_trend_data = this._get_default_profit_trend_data();
        }
    }

    async fetch_additional_data_with_dates(start_date, end_date) {
        try {
            console.log('Fetching additional data for custom dates:', start_date, end_date);
            
            // Get sales target data (no date filter needed)
            try {
                const targetData = await this.orm.call('pos.order', 'get_sales_target_data', []);
                this.state.sales_target = targetData || {
                    target_amount: 0,
                    current_amount: 0,
                    achievement_percentage: 0,
                    period: 'Current Month'
                };
            } catch (targetError) {
                console.error('Error fetching target data:', targetError);
                this.state.sales_target = {
                    target_amount: 0,
                    current_amount: 0,
                    achievement_percentage: 0,
                    period: 'Current Month'
                };
            }
            
            // For custom date range, use get_peak_hours_with_dates
            try {
                console.log('Calling get_peak_hours_with_dates with:', start_date, end_date);
                const peakHoursData = await this.orm.call('pos.order', 'get_peak_hours_with_dates', [
                    start_date, 
                    end_date
                ]);
                
                console.log('Peak hours data received:', {
                    hours_count: peakHoursData.all_hours ? peakHoursData.all_hours.length : 0,
                    filter_type: peakHoursData.filter_type,
                    total_sales: peakHoursData.total_sales
                });
                
                this.state.peak_hours_data = peakHoursData || {
                    all_hours: [],
                    time_periods: [],
                    total_sales: 0,
                    total_orders: 0,
                    peak_hour: null,
                    filter_type: 'custom'
                };
                
            } catch (peakHoursError) {
                console.error('Error fetching peak hours with custom dates:', peakHoursError);
                // Fallback to sample data
                this.state.peak_hours_data = this._get_sample_peak_hours_data();
                this.state.peak_hours_data.filter_type = 'custom';
            }
            
            // Get top customers - use simpler approach
            try {
                console.log('Calling get_top_customers_detailed_with_dates with:', 5, start_date, end_date);
                const topCustomers = await this.orm.call('pos.order', 'get_top_customers_detailed_with_dates', [
                    5, 
                    start_date, 
                    end_date
                ]);
                this.state.top_customers_detailed = topCustomers || [];
                console.log('Top customers loaded:', this.state.top_customers_detailed.length);
            } catch (customerError) {
                console.error('Error fetching top customers with custom dates:', customerError);
                // Try alternative method
                try {
                    const topCustomers = await this.orm.call('pos.order', 'get_top_customers_detailed', [5, 'all']);
                    this.state.top_customers_detailed = topCustomers || [];
                } catch (fallbackError) {
                    console.error('Fallback also failed:', fallbackError);
                    this.state.top_customers_detailed = this._get_sample_customer_data();
                }
            }
            
        } catch (error) {
            console.error('General error in fetch_additional_data_with_dates:', error);
            // Set default data on error
            this.state.sales_target = {
                target_amount: 0,
                current_amount: 0,
                achievement_percentage: 0,
                period: 'Current Month'
            };
            this.state.peak_hours_data = this._get_sample_peak_hours_data();
            this.state.peak_hours_data.filter_type = 'custom';
            this.state.top_customers_detailed = this._get_sample_customer_data();
        }
    }

    // Add sample customer data method
    _get_sample_customer_data() {
        return [
            {
                id: 1,
                customer_name: 'John Doe',
                order_count: 5,
                total_spent: 1250.50,
                avg_order_value: 250.10,
                last_order_date: new Date(),
                total_spent_display: 'GH¢1,250.50',
                avg_order_value_display: 'GH¢250.10',
                last_order_date_display: new Date().toLocaleDateString() + ' ' + new Date().toLocaleTimeString()
            },
            {
                id: 2,
                customer_name: 'Jane Smith',
                order_count: 3,
                total_spent: 850.75,
                avg_order_value: 283.58,
                last_order_date: new Date(Date.now() - 86400000), // yesterday
                total_spent_display: 'GH¢850.75',
                avg_order_value_display: 'GH¢283.58',
                last_order_date_display: new Date(Date.now() - 86400000).toLocaleDateString()
            }
        ];
    }


    async debug_peak_hours() {
        console.log('=== Debug Peak Hours ===');
        
        try {
            const filters = ['today', 'yesterday', 'last_week', 'last_month', 'this_month', 'last_year'];
            
            for (const filter of filters) {
                console.log(`Testing filter: ${filter}`);
                const data = await this.orm.call('pos.order', 'get_peak_hours', [filter]);
                console.log(`Filter ${filter}:`, {
                    hours_count: data.all_hours ? data.all_hours.length : 0,
                    total_sales: data.total_sales || 0,
                    filter_type: data.filter_type || 'unknown',
                    start_date: data.start_date || 'N/A',
                    end_date: data.end_date || 'N/A'
                });
            }
            
            // Test current filter
            const currentData = await this.orm.call('pos.order', 'get_peak_hours', [this.state.date_range]);
            console.log('Current filter data:', currentData);
            
        } catch (error) {
            console.error('Debug error:', error);
        }
    }

    // Call this in setup to test:
    // await this.debug_peak_hours();

    async fetch_data() {
        try {
            const result = await this.orm.call('pos.order', 'get_refund_details', []);
            this.state.total_sale = result['total_sale'];
            this.state.total_order_count = result['total_order_count'];
            this.state.total_refund_count = result['total_refund_count'];
            this.state.total_session = result['total_session'];
            this.state.today_refund_total = result['today_refund_total'];
            this.state.today_sale = result['today_sale'];
            const data = await this.orm.call('pos.order', 'get_details', []);
            this.state.payment_details = data['payment_details'];
            
            this.state.top_salesperson = data['salesperson'];
            this.state.selling_product = data['selling_product'];
        } catch (error) {
            console.error('Error fetching data:', error);
            this.show_notification('Error loading dashboard data', 'danger');
        }
    }
    
    async fetch_additional_data() {
        try {
            const targetData = await this.orm.call('pos.order', 'get_sales_target_data', []);
            this.state.sales_target = targetData;
            
            // For peak hours - get full 24-hour distribution
            try {
                const peakHoursData = await this.orm.call('pos.order', 'get_peak_hours', [this.state.date_range]);
                this.state.peak_hours_data = peakHoursData || {
                    all_hours: [],
                    time_periods: [],
                    total_sales: 0,
                    total_orders: 0,
                    peak_hour: null
                };
                
                console.log('Peak hours data loaded:', {
                    hours_count: this.state.peak_hours_data.all_hours.length,
                    periods: this.state.peak_hours_data.time_periods,
                    total_sales: this.state.peak_hours_data.total_sales
                });
                
            } catch (error) {
                console.error('Error fetching peak hours:', error);
                // Set sample data if error
                this.state.peak_hours_data = this._get_sample_peak_hours_data();
            }
            
            const topCustomers = await this.orm.call('pos.order', 'get_top_customers_detailed', [5, this.state.date_range]);
            this.state.top_customers_detailed = topCustomers || [];
        } catch (error) {
            console.error('Error fetching additional data:', error);
        }
    }

    _get_sample_peak_hours_data() {
        // Create sample 24-hour data
        const sampleHours = [];
        for (let hour = 0; hour < 24; hour++) {
            let period;
            if (hour >= 6 && hour < 9) period = 'Early Morning (6AM-9AM)';
            else if (hour >= 9 && hour < 12) period = 'Morning (9AM-12PM)';
            else if (hour >= 12 && hour < 14) period = 'Lunch (12PM-2PM)';
            else if (hour >= 14 && hour < 17) period = 'Afternoon (2PM-5PM)';
            else if (hour >= 17 && hour < 21) period = 'Evening (5PM-9PM)';
            else if (hour >= 21) period = 'Late Night (9PM-12AM)';
            else period = 'Night (12AM-6AM)';
            
            // Create realistic sample sales pattern
            let sales;
            if (hour >= 9 && hour <= 11) sales = 800 + (hour - 9) * 200;
            else if (hour >= 12 && hour <= 14) sales = 1200;
            else if (hour >= 17 && hour <= 19) sales = 1500;
            else if (hour === 20) sales = 2000;
            else sales = 100 + (hour * 20);
            
            sampleHours.push({
                hour: hour,
                hour_display: `${hour.toString().padStart(2, '0')}:00`,
                order_count: Math.max(1, Math.floor(sales / 100)),
                total_amount: sales,
                period: period
            });
        }
        
        // Calculate peak hour
        const peakHour = sampleHours.reduce((max, hour) => 
            hour.total_amount > max.total_amount ? hour : max, sampleHours[0]);
        
        return {
            all_hours: sampleHours,
            time_periods: this._calculate_period_summary(sampleHours),
            total_sales: sampleHours.reduce((sum, hour) => sum + hour.total_amount, 0),
            total_orders: sampleHours.reduce((sum, hour) => sum + hour.order_count, 0),
            peak_hour: peakHour
        };
    }

    _calculate_period_summary(hours) {
        const periodSummary = {};
        
        hours.forEach(hour => {
            const period = hour.period;
            if (!periodSummary[period]) {
                periodSummary[period] = {
                    period: period,
                    total_amount: 0,
                    order_count: 0,
                    hours: []
                };
            }
            periodSummary[period].total_amount += hour.total_amount;
            periodSummary[period].order_count += hour.order_count;
            periodSummary[period].hours.push(hour.hour);
        });
        
        return Object.values(periodSummary).sort((a, b) => b.total_amount - a.total_amount);
    }
    
    setup_event_listeners() {
        // Filter change
        const filterSelect = document.getElementById('date_filter');
        if (filterSelect) {
            filterSelect.addEventListener('change', (e) => this.on_filter_change(e));
        }
        
        // Chart type change
        const chartTypeSelect = document.getElementById('chart_type');
        if (chartTypeSelect) {
            chartTypeSelect.addEventListener('change', (e) => this.on_chart_type_change(e));
        }
        
        // Sales period change
        const salesPeriodSelect = document.getElementById('sales_period');
        if (salesPeriodSelect) {
            salesPeriodSelect.addEventListener('change', (e) => this.onclick_pos_sales(e));
        }
    }
    
    async on_filter_change(event) {
        const filter = event.target.value;
        this.state.current_filter = filter;
        
        // Save state
        this.saveState();
        
        await this.fetch_additional_data();
        await this.render_all_charts();
        
        this.show_notification(`Filter updated to: ${filter}`, 'info');
    }
    
    async on_chart_type_change(event) {
        const chartType = event.target.value;
        this.state.current_chart_type = chartType;
        
        // Save state
        this.saveState();
        
        // Re-render detailed chart
        await this.render_sales_chart('pos_hourly_sales');
        
        this.show_notification(`Chart type changed to: ${chartType}`, 'info');
    }
    
    async render_all_charts() {
        try {
            console.log('Starting to render all charts...');
            
            // Destroy existing charts first
            Object.keys(this.charts).forEach(key => {
                if (this.charts[key]) {
                    try {
                        this.charts[key].destroy();
                    } catch (e) {
                        console.warn(`Error destroying chart ${key}:`, e);
                    }
                    this.charts[key] = null;
                }
            });
            
            // Render charts in order
            await this.render_sales_chart('pos_hourly_sales');
            await this.render_target_chart();
            await this.render_products_chart();
            await this.render_categories_chart();
            await this.render_hours_chart();
            await this.render_profit_trend_chart();
            await this.render_profit_margin_chart();
            await this.render_expense_revenue_chart();  // Add this line
            
            console.log('All charts rendered successfully');
        } catch (error) {
            console.error('Error rendering all charts:', error);
            this.show_notification('Error rendering some charts', 'warning');
        }
    }

    getMonthName(monthNumber) {
        const monthNames = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ];
        return monthNames[monthNumber - 1] || '';
    }
        formatLargeNumber(value) {
        if (value >= 1000000) {
            return (value / 1000000).toFixed(1) + 'M';
        } else if (value >= 1000) {
            return (value / 1000).toFixed(1) + 'K';
        }
        return value.toFixed(0);
    }

    // Add this to setup method for event listeners
    setup_event_listeners() {
        // ... existing event listeners ...
        
        // Expense vs Revenue year change
        const expenseYearSelect = document.getElementById('expense_year');
        if (expenseYearSelect) {
            expenseYearSelect.addEventListener('change', (e) => this.on_expense_year_change(e));
        }
        
        // Expense vs Revenue month change
        const expenseMonthSelect = document.getElementById('expense_month');
        if (expenseMonthSelect) {
            expenseMonthSelect.addEventListener('change', (e) => this.on_expense_month_change(e));
        }
    }

    on_expense_year_change(event) {
        const year = parseInt(event.target.value);
        if (year) {
            this.change_expense_year(year);
        }
    }

    on_expense_month_change(event) {
        const month = event.target.value === 'all' ? null : parseInt(event.target.value);
        this.change_expense_month(month);
    }


    
    async render_sales_chart(option) {
        const canvas = document.getElementById('sales_chart');
        if (!canvas) return;
        
        if (this.charts.sales) {
            this.charts.sales.destroy();
        }
        
        try {
            const arrays = await this.orm.call('pos.order', 'get_department', [option]);
            const ctx = canvas.getContext('2d');
            
            this.charts.sales = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: arrays[1],
                    datasets: [{
                        label: arrays[2],
                        data: arrays[0],
                        backgroundColor: 'rgba(54, 162, 235, 0.2)',
                        borderColor: 'rgba(54, 162, 235, 1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: true,
                            position: 'top',
                        },
                        title: {
                            display: true,
                            text: 'Sales Trend',
                            font: {
                                size: 16
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Amount (GH¢)'
                            }
                        },
                        x: {
                            title: {
                                display: true,
                                text: arrays[2]
                            }
                        }
                    }
                }
            });
        } catch (error) {
            console.error('Error rendering sales chart:', error);
        }
    }
    
    render_target_chart() {
        const canvas = document.getElementById('target_chart');
        if (!canvas) return;
        
        if (this.charts.target) {
            this.charts.target.destroy();
        }
        
        const ctx = canvas.getContext('2d');
        const target = this.state.sales_target.target_amount || 0;
        const current = this.state.sales_target.current_amount || 0;
        const remaining = Math.max(0, target - current);
        
        this.charts.target = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Achieved', 'Remaining'],
                datasets: [{
                    data: [current, remaining],
                    backgroundColor: [
                        'rgba(75, 192, 192, 0.8)',
                        'rgba(255, 99, 132, 0.2)'
                    ],
                    borderColor: [
                        'rgba(75, 192, 192, 1)',
                        'rgba(255, 99, 132, 1)'
                    ],
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.parsed;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = total > 0 ? Math.round((value / total) * 100) : 0;
                                return `${label}: ${value.toFixed(2)} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });
    }

    async fetch_profit_data() {
        try {
            console.log('Fetching profit data for filter:', this.state.date_range);
            
            // First, get the date range
            const dateRange = this.getDateRange();
            console.log('Date range:', dateRange);
            
            let profitData, profitSummary, profitableCategories, profitTrend;
            
            if (this.state.date_range === 'custom') {
                // Use date-specific methods for custom range
                profitData = await this.orm.call('pos.order', 'get_profit_margin_analysis_with_dates', [
                    dateRange.start_date, 
                    dateRange.end_date
                ]);
                
                profitSummary = await this.orm.call('pos.order', 'get_profit_summary_with_dates', [
                    dateRange.start_date, 
                    dateRange.end_date
                ]);
                
                profitableCategories = await this.orm.call('pos.order', 'get_top_profitable_categories_with_dates', [
                    5, 
                    dateRange.start_date, 
                    dateRange.end_date
                ]);
                
                // FIXED: Use the correct method for custom date range profit trend
                profitTrend = await this.orm.call('pos.order', 'get_profit_trend_analysis_with_dates', [
                    dateRange.start_date, 
                    dateRange.end_date
                ]);
                
            } else {
                // Use filter-based methods for predefined ranges
                profitData = await this.orm.call('pos.order', 'get_profit_margin_analysis', [this.state.date_range]);
                profitSummary = await this.orm.call('pos.order', 'get_profit_summary', [this.state.date_range]);
                profitableCategories = await this.orm.call('pos.order', 'get_top_profitable_categories', [5, this.state.date_range]);
                
                // Get profit trend for the selected filter
                profitTrend = await this.orm.call('pos.order', 'get_profit_trend_analysis', [this.state.date_range]);
            }
            
            console.log('Profit data loaded:', {
                margin_data_count: profitData ? profitData.length : 0,
                summary: profitSummary,
                categories_count: profitableCategories ? profitableCategories.length : 0,
                trend_data: profitTrend
            });
            
            this.state.profit_margin_data = profitData || [];
            this.state.profit_summary = profitSummary || this._get_default_profit_summary();
            this.state.top_profitable_categories = profitableCategories || [];
            this.state.profit_trend_data = profitTrend || this._get_default_profit_trend_data();
            
        } catch (error) {
            console.error('Error fetching profit data:', error);
            this.show_notification('Error loading profit margin data', 'danger');
            
            // Set default data
            this.state.profit_margin_data = [];
            this.state.profit_summary = this._get_default_profit_summary();
            this.state.top_profitable_categories = [];
            this.state.profit_trend_data = this._get_default_profit_trend_data();
        }
    }

    _get_default_profit_summary() {
        const company = this.user.companyId;
        // In real implementation, you'd get the currency symbol from company
        return {
            total_revenue_display: 'GH¢ 0.00', // Changed from $
            total_cost_display: 'GH¢ 0.00', // Changed from $
            total_profit_display: 'GH¢ 0.00', // Changed from $
            overall_margin_percentage_display: '0%',
            total_orders: 0,
            avg_profit_per_order_display: 'GH¢ 0.00'
        };
    }

    _get_default_profit_trend_data() {
        return {
            labels: ['No Data'],
            datasets: [{
                label: 'Profit',
                data: [0],
                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                borderColor: 'rgba(75, 192, 192, 1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4
            }],
            type: 'line',
            x_axis_label: 'No Data Available',
            total_profit: 0,
            total_revenue: 0,
            total_cost: 0
        };
    }

    _get_default_profit_summary() {
        return {
            total_revenue_display: 'GH¢0.00',
            total_cost_display: 'GH¢0.00',
            total_profit_display: 'GH¢0.00',
            overall_margin_percentage_display: '0%',
            total_orders: 0,
            avg_profit_per_order_display: 'GH¢0.00'
        };
    }
    
    async render_profit_trend_chart() {
        const canvas = document.getElementById('profit_trend_chart');
        if (!canvas) {
            console.log('Profit trend chart canvas not found');
            return;
        }
        
        // Destroy existing chart
        if (this.charts.profit_trend) {
            this.charts.profit_trend.destroy();
        }
        
        const ctx = canvas.getContext('2d');
        
        // Check if we have data
        if (!this.state.profit_trend_data) {
            // Show "Loading..." or similar
            this.renderEmptyChart(ctx, 'Loading data...');
            return;
        }
        
        const data = this.state.profit_trend_data;
        
        // Check for no data flag
        if (data.no_data === true || !data.labels || data.labels.length === 0) {
            this.renderEmptyChart(ctx, data.x_axis_label === 'No Data' ? 'No Data Available' : 'No Data Available');
            return;
        }
        
        // Create the actual chart with real data
        this.charts.profit_trend = new Chart(ctx, {
            type: data.type || 'line',
            data: {
                labels: data.labels || [],
                datasets: data.datasets || []
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    title: {
                        display: true,
                        text: data.x_axis_label === 'No Data' ? 'No Data Available' : 'Profit Trend Analysis',
                        font: {
                            size: 14,
                            weight: 'bold'
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Amount (GH¢)'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: data.x_axis_label || 'Period'
                        }
                    }
                }
            }
        });
    }
    
    async render_profit_margin_chart() {
        const canvas = document.getElementById('profit_margin_chart');
        if (!canvas || !this.state.profit_margin_data || this.state.profit_margin_data.length === 0) return;
        
        if (this.charts.profit_margin) {
            this.charts.profit_margin.destroy();
        }
        
        const ctx = canvas.getContext('2d');
        const data = this.state.profit_margin_data.slice(0, 5); // Top 5
        
        // Determine chart type
        const chartType = this.state.profit_chart_type || 'doughnut';
        
        if (chartType === 'doughnut' || chartType === 'pie') {
            // Create donut/pie chart showing profit distribution
            const chartData = data.map(item => item.total_profit || 0);
            const chartLabels = data.map(item => {
                // Truncate long product names
                const name = item.product_name || 'Unknown';
                return name.length > 20 ? name.substring(0, 20) + '...' : name;
            });
            
            // Calculate total profit for center display
            const totalProfit = chartData.reduce((sum, value) => sum + value, 0);
            
            const colors = [
                'rgba(255, 99, 132, 0.8)',
                'rgba(54, 162, 235, 0.8)',
                'rgba(255, 206, 86, 0.8)',
                'rgba(75, 192, 192, 0.8)',
                'rgba(153, 102, 255, 0.8)'
            ];
            
            // Create donut chart with center text
            this.charts.profit_margin = new Chart(ctx, {
                type: chartType,
                data: {
                    labels: chartLabels,
                    datasets: [{
                        label: 'Profit',
                        data: chartData,
                        backgroundColor: colors,
                        borderColor: colors.map(color => color.replace('0.8', '1')),
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: chartType === 'doughnut' ? '80%' : 0,
                    plugins: {
                        legend: {
                            position: 'right',
                            labels: {
                                padding: 20,
                                usePointStyle: true,
                                pointStyle: 'circle',
                                font: {
                                    size: 12
                                }
                            }
                        },
                        title: {
                            display: true,
                            text: 'Top Products Profit Distribution',
                            font: {
                                size: 16,
                                weight: 'bold'
                            },
                            position:'left'
                            
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const label = context.label || '';
                                    const value = context.parsed || 0;
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                    const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                                    
                                    // Find the product data
                                    const productIndex = context.dataIndex;
                                    const product = data[productIndex];
                                    const margin = product ? product.profit_margin_percentage || 0 : 0;
                                    
                                    return [
                                        `${label}: GH¢${value.toFixed(2)}`,  // Changed from $
                                        `Share: ${percentage}% of total`,
                                        `Margin: ${margin.toFixed(1)}%`
                                    ];
                                }
                            }
                        },
                        centerText: {
                            text: `GH¢${totalProfit.toFixed(2)}`,  // Changed from $
                            color: '#4CAF50',
                            fontStyle: 'bold',
                            fontSize: 24,
                            sidePadding: 20
                        }
                    }
                },
                plugins: [{
                    id: 'centerText',
                    afterDraw: (chart) => {
                        if (chart.config.type === 'doughnut') {
                            const {ctx} = chart;
                            const centerX = (chart.chartArea.left + chart.chartArea.right) / 2;
                            const centerY = (chart.chartArea.top + chart.chartArea.bottom) / 2;
                            
                            // Save context
                            ctx.save();
                            
                            // Draw "Total Profit" text
                            ctx.font = 'bold 14px Arial';
                            ctx.fillStyle = '#666';
                            ctx.textAlign = 'center';
                            ctx.textBaseline = 'bottom';
                            ctx.fillText('Total Profit', centerX, centerY - 10);
                            
                            // Draw profit amount
                            const options = chart.options.plugins.centerText || {};
                            ctx.font = `${options.fontStyle || 'bold'} ${options.fontSize || 24}px Arial`;
                            ctx.fillStyle = options.color || '#4CAF50';
                            ctx.textBaseline = 'top';
                            ctx.fillText(options.text || '', centerX, centerY + 5);
                            
                            ctx.restore();
                        }
                    }
                }]
            });
        } else {
            // Bar chart code
            this.charts.profit_margin = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.map(item => {
                        const name = item.product_name || 'Unknown';
                        return name.length > 15 ? name.substring(0, 15) + '...' : name;
                    }),
                    datasets: [
                        {
                            label: 'Revenue',
                            data: data.map(item => item.total_revenue || 0),
                            backgroundColor: 'rgba(54, 162, 235, 0.7)',
                            borderColor: 'rgba(54, 162, 235, 1)',
                            borderWidth: 1
                        },
                        {
                            label: 'Cost',
                            data: data.map(item => item.total_cost || 0),
                            backgroundColor: 'rgba(255, 99, 132, 0.7)',
                            borderColor: 'rgba(255, 99, 132, 1)',
                            borderWidth: 1
                        },
                        {
                            label: 'Profit',
                            data: data.map(item => item.total_profit || 0),
                            backgroundColor: 'rgba(75, 192, 192, 0.7)',
                            borderColor: 'rgba(75, 192, 192, 1)',
                            borderWidth: 1
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                        },
                        title: {
                            display: true,
                            text: 'Top Products by Profit Margin',
                            font: {
                                size: 16,
                                weight: 'bold'
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    let label = context.dataset.label || '';
                                    if (label) {
                                        label += ': ';
                                    }
                                    if (context.parsed.y !== null) {
                                        const productIndex = context.dataIndex;
                                        const product = data[productIndex];
                                        if (context.dataset.label === 'Profit' && product) {
                                            return `${label}GH¢${context.parsed.y.toFixed(2)} (${product.profit_margin_percentage.toFixed(1)}%)`;  // Changed from $
                                        } else {
                                            return `${label}GH¢${context.parsed.y.toFixed(2)}`;  // Changed from $
                                        }
                                    }
                                    return label;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            title: {
                                display: true,
                                text: 'Products',
                                font: {
                                    weight: 'bold'
                                }
                            }
                        },
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Amount (GH¢)',  // Changed from ($)
                                font: {
                                    weight: 'bold'
                                }
                            },
                            ticks: {
                                callback: function(value) {
                                    return 'GH¢' + value;  // Changed from $
                                }
                            }
                        }
                    }
                }
            });
        }
    }

    render_profit_trend_chart() {
        const canvas = document.getElementById('profit_trend_chart');
        if (!canvas) {
            console.log('Profit trend chart canvas not found');
            return;
        }
        
        // Destroy existing chart
        if (this.charts.profit_trend) {
            this.charts.profit_trend.destroy();
        }
        
        const ctx = canvas.getContext('2d');
        
        // Check if we have data
        if (!this.state.profit_trend_data) {
            // Show "Loading..." or similar
            this.renderEmptyChart(ctx, 'Loading data...');
            return;
        }
        
        const data = this.state.profit_trend_data;
        
        // Check for no data flag
        if (data.no_data === true || !data.labels || data.labels.length === 0) {
            this.renderEmptyChart(ctx, data.x_axis_label === 'No Data' ? 'No Data Available' : 'No Data Available');
            return;
        }
        
        // Create the actual chart with real data
        this.charts.profit_trend = new Chart(ctx, {
            type: data.type || 'line',
            data: {
                labels: data.labels || [],
                datasets: data.datasets || []
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    title: {
                        display: true,
                        text: data.x_axis_label === 'No Data' ? 'No Data Available' : 'Profit Trend Analysis',
                        font: {
                            size: 14,
                            weight: 'bold'
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Amount (GH¢)'  // Changed from ($)
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: data.x_axis_label || 'Period'
                        }
                    }
                }
            }
        });
    }

    async render_products_chart() {
        const canvas = document.getElementById('products_chart');
        if (!canvas) {
            console.error('Products chart canvas not found');
            return;
        }
        
        if (this.charts.products) {
            this.charts.products.destroy();
        }
        
        try {
            console.log('Top products data for chart:', this.state.top_products_data);
            
            const ctx = canvas.getContext('2d');
            
            // Extract product names and quantities
            let productNames = [];
            let quantities = [];
            
            if (Array.isArray(this.state.top_products_data) && this.state.top_products_data.length === 2) {
                quantities = this.state.top_products_data[0] || [];
                productNames = this.state.top_products_data[1] || [];
                
                if (!Array.isArray(quantities)) quantities = [];
                if (!Array.isArray(productNames)) productNames = [];
            } else {
                console.error('Unexpected data structure for top products:', this.state.top_products_data);
                quantities = [];
                productNames = [];
            }
            
            console.log('Raw product names:', productNames);
            
            // Extract translated names
            const extractedNames = productNames.map(name => {
                const extracted = this.extractTranslatedName(name);
                console.log(`Extracted name: ${name} -> ${extracted}`);
                return extracted;
            });
            
            // Take only top 5 products
            const topProductNames = extractedNames.slice(0, 5);
            const topQuantities = quantities.slice(0, 5);
            
            // Convert quantities to numbers
            const numberQuantities = topQuantities.map(qty => {
                const num = parseFloat(qty);
                return isNaN(num) ? 0 : num;
            });
            
            // Truncate long product names for display
            const displayNames = topProductNames.map(name => {
                const cleanName = name || 'Unknown Product';
                if (cleanName.length > 15) {
                    return cleanName.substring(0, 12) + '...';
                }
                return cleanName;
            });
            
            const colors = [
                'rgba(255, 99, 132, 0.7)',
                'rgba(54, 162, 235, 0.7)',
                'rgba(255, 206, 86, 0.7)',
                'rgba(75, 192, 192, 0.7)',
                'rgba(153, 102, 255, 0.7)'
            ];
            
            this.charts.products = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: displayNames,
                    datasets: [{
                        label: 'Quantity Sold',
                        data: numberQuantities,
                        backgroundColor: colors,
                        borderColor: colors.map(color => color.replace('0.7', '1')),
                        borderWidth: 1,
                        borderRadius: 5
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        },
                        title: {
                            display: true,
                            text: `Top Products (${this.state.date_range})`,
                            font: {
                                size: 14,
                                weight: 'bold'
                            }
                        },
                        tooltip: {
                            callbacks: {
                                title: function(context) {
                                    // Show full name in tooltip
                                    const index = context[0].dataIndex;
                                    return topProductNames[index] || 'Unknown';
                                },
                                label: function(context) {
                                    return `Quantity: ${context.parsed.y} units`;
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Quantity Sold'
                            },
                            ticks: {
                                stepSize: 1
                            }
                        },
                        x: {
                            title: {
                                display: true,
                                text: 'Products'
                            },
                            ticks: {
                                autoSkip: false,
                                maxRotation: 45,
                                minRotation: 45
                            }
                        }
                    }
                }
            });
            
        } catch (error) {
            console.error('Error rendering products chart:', error);
            
            // Create a simple fallback chart
            const ctx = canvas.getContext('2d');
            this.charts.products = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: ['No Data'],
                    datasets: [{
                        label: 'Quantity Sold',
                        data: [0],
                        backgroundColor: 'rgba(201, 203, 207, 0.7)',
                        borderColor: 'rgba(201, 203, 207, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        },
                        title: {
                            display: true,
                            text: 'No Data Available'
                        }
                    }
                }
            });
        }
    }
    
    async on_filter_change(event) {
        const filter = event.target.value;
        this.state.current_filter = filter;
        
        await this.fetch_additional_data();
        await this.fetch_profit_data();
        await this.render_all_charts();
        
        this.show_notification(`Filter updated to: ${filter}`, 'info');
    }
    
    // Add method to view product details
    view_product_details = (productId) => {
        console.log('Viewing product details for ID:', productId);
        if (!productId) {
            this.notification.add('No product ID available', {type: 'danger'});
            return;
        }
        
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: 'product.product',
            res_id: productId,
            views: [[false, 'form']],
            target: 'current'
        });
    };
    
    format_currency(value) {
        if (value === undefined || value === null) return '';
        try {
            const numValue = parseFloat(value);
            if (isNaN(numValue)) return '';
            return `PKR ${numValue.toFixed(2)}`;
        } catch (error) {
            console.error('Error formatting currency:', error);
            return `PKR ${value}`;
        }
    }
    
    

    // Helper method to generate colors
    generateColors(count, baseColor) {
        const colors = [];
        for (let i = 0; i < count; i++) {
            colors.push(baseColor);
        }
        return colors;
    }

    async render_categories_chart() {
        const canvas = document.getElementById('categories_chart');
        if (!canvas) return;
        
        if (this.charts.categories) {
            this.charts.categories.destroy();
        }
        
        try {
            console.log('Top categories data for chart:', this.state.top_categories_data);
            
            const ctx = canvas.getContext('2d');
            
            // Extract category names and quantities
            let categoryNames = [];
            let quantities = [];
            
            // Check if data is in expected format [quantities[], names[]]
            if (Array.isArray(this.state.top_categories_data) && this.state.top_categories_data.length === 2) {
                quantities = this.state.top_categories_data[0] || [];
                categoryNames = this.state.top_categories_data[1] || [];
                
                if (!Array.isArray(quantities)) quantities = [];
                if (!Array.isArray(categoryNames)) categoryNames = [];
            } else {
                console.error('Unexpected data structure for top categories:', this.state.top_categories_data);
                quantities = [];
                categoryNames = [];
            }
            
            console.log('Extracted category names:', categoryNames);
            console.log('Extracted quantities:', quantities);
            
            // Take only top 5 categories
            const topCategoryNames = categoryNames.slice(0, 5);
            const topQuantities = quantities.slice(0, 5);
            
            // Convert category names to strings
            const stringCategoryNames = topCategoryNames.map(name => {
                if (typeof name === 'object') {
                    if (name && typeof name === 'object') {
                        return name.product_category || name.category_name || name.name || 
                            JSON.stringify(name).substring(0, 20) + '...';
                    }
                    return 'Uncategorized';
                }
                return String(name || 'Uncategorized');
            });
            
            // Convert quantities to numbers
            const numberQuantities = topQuantities.map(qty => {
                const num = parseFloat(qty);
                return isNaN(num) ? 0 : num;
            });
            
            // Truncate long category names for display
            const displayNames = stringCategoryNames.map(name => {
                if (name.length > 20) {
                    return name.substring(0, 17) + '...';
                }
                return name;
            });
            
            this.charts.categories = new Chart(ctx, {
                type: 'pie',
                data: {
                    labels: displayNames,
                    datasets: [{
                        data: numberQuantities,
                        backgroundColor: [
                            'rgba(255, 99, 132, 0.7)',
                            'rgba(54, 162, 235, 0.7)',
                            'rgba(255, 206, 86, 0.7)',
                            'rgba(75, 192, 192, 0.7)',
                            'rgba(153, 102, 255, 0.7)'
                        ],
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'right',
                            labels: {
                                font: {
                                    size: 11
                                }
                            }
                        },
                        title: {
                            display: true,
                            text: `Top Categories (${this.state.date_range})`,
                            font: {
                                size: 14,
                                weight: 'bold'
                            }
                        },
                        tooltip: {
                            callbacks: {
                                title: function(context) {
                                    // Show full name in tooltip
                                    const index = context[0].dataIndex;
                                    return stringCategoryNames[index] || 'Uncategorized';
                                },
                                label: function(context) {
                                    const label = context.label || '';
                                    const value = context.parsed;
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                    const percentage = total > 0 ? Math.round((value / total) * 100) : 0;
                                    return `${label}: ${value} units (${percentage}%)`;
                                }
                            }
                        }
                    }
                }
            });
        } catch (error) {
            console.error('Error rendering categories chart:', error);
        }
    }
    
    getEnhancedPeakHoursAnalysis() {
        const peakHours = this.state.peak_hours || [];
        if (peakHours.length === 0) return {};
        
        // Calculate statistics
        const totalSales = peakHours.reduce((sum, hour) => sum + (hour.total_amount || 0), 0);
        const totalOrders = peakHours.reduce((sum, hour) => sum + (hour.order_count || 0), 0);
        const maxHour = peakHours.reduce((max, hour) => 
            (hour.total_amount || 0) > (max.total_amount || 0) ? hour : max, 
            peakHours[0] || {}
        );
        
        return {
            peakHour: maxHour.hour_display || 'N/A',
            peakHourSales: maxHour.total_amount || 0,
            totalSales: totalSales,
            totalOrders: totalOrders,
            avgOrderValue: totalOrders > 0 ? totalSales / totalOrders : 0
        };
    }


    render_hours_chart() {
        const canvas = document.getElementById('hours_chart');
        if (!canvas) return;
        
        if (this.charts.hours) {
            this.charts.hours.destroy();
        }
        
        const ctx = canvas.getContext('2d');
        const chartType = this.state.peak_hours_chart_type || 'curve';
        
        // Get data
        const hoursData = this.state.peak_hours_data?.all_hours || [];
        if (hoursData.length === 0) {
            console.log('No hours data available');
            return;
        }
        
        // Sort by hour
        hoursData.sort((a, b) => a.hour - b.hour);
        
        const labels = hoursData.map(h => h.hour_display);
        const data = hoursData.map(h => h.total_amount);
        
        // Define colors based on time periods
        const backgroundColors = hoursData.map(h => {
            if (h.hour >= 9 && h.hour < 12) return 'rgba(255, 206, 86, 0.7)'; // Morning - yellow
            else if (h.hour >= 12 && h.hour < 14) return 'rgba(75, 192, 192, 0.7)'; // Lunch - teal
            else if (h.hour >= 17 && h.hour < 21) return 'rgba(153, 102, 255, 0.7)'; // Evening - purple
            else if (h.hour >= 21) return 'rgba(255, 99, 132, 0.7)'; // Late night - red
            else return 'rgba(201, 203, 207, 0.7)'; // Other times - gray
        });
        
        const borderColors = hoursData.map(h => {
            if (h.hour >= 9 && h.hour < 12) return 'rgba(255, 206, 86, 1)'; // Morning
            else if (h.hour >= 12 && h.hour < 14) return 'rgba(75, 192, 192, 1)'; // Lunch
            else if (h.hour >= 17 && h.hour < 21) return 'rgba(153, 102, 255, 1)'; // Evening
            else if (h.hour >= 21) return 'rgba(255, 99, 132, 1)'; // Late night
            else return 'rgba(201, 203, 207, 1)'; // Other times
        });
        
        if (chartType === 'bar') {
            // Bar chart showing 24 hours
            this.charts.hours = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Sales Amount',
                        data: data,
                        backgroundColor: backgroundColors,
                        borderColor: borderColors,
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        },
                        title: {
                            display: true,
                            text: '24-Hour Sales Distribution',
                            font: {
                                size: 16,
                                weight: 'bold'
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const hour = context.dataIndex;
                                    const hourData = hoursData[hour];
                                    const period = hourData?.period || '';
                                    return [
                                        `Sales: GH¢${context.parsed.y.toFixed(2)}`,  // Changed from $
                                        `Period: ${period}`,
                                        `Orders: ${hourData?.order_count || 0}`
                                    ];
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Sales Amount (GH¢)'  // Changed from ($)
                            },
                            ticks: {
                                callback: function(value) {
                                    return 'GH¢' + value;  // Changed from $
                                }
                            }
                        },
                        x: {
                            title: {
                                display: true,
                                text: 'Hour of Day'
                            },
                            ticks: {
                                autoSkip: false,
                                maxRotation: 45,
                                minRotation: 45
                            }
                        }
                    }
                }
            });
        } else {
            // Line/Curve chart
            const isCurve = chartType === 'curve';
            
            this.charts.hours = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Sales Amount',
                        data: data,
                        backgroundColor: isCurve ? 'rgba(54, 162, 235, 0.1)' : 'transparent',
                        borderColor: 'rgba(54, 162, 235, 1)',
                        borderWidth: 3,
                        fill: isCurve,
                        tension: isCurve ? 0.4 : 0,
                        pointBackgroundColor: borderColors,
                        pointBorderColor: '#fff',
                        pointBorderWidth: 2,
                        pointRadius: 4,
                        pointHoverRadius: 7,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        },
                        title: {
                            display: true,
                            text: '24-Hour Sales Trend',
                            font: {
                                size: 16,
                                weight: 'bold'
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const hour = context.dataIndex;
                                    const hourData = hoursData[hour];
                                    return [
                                        `Hour: ${hourData?.hour_display || ''}`,
                                        `Sales: GH¢${context.parsed.y.toFixed(2)}`,  // Changed from $
                                        `Period: ${hourData?.period || ''}`
                                    ];
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Sales Amount (GH¢)'  // Changed from ($)
                            },
                            ticks: {
                                callback: function(value) {
                                    return 'GH¢' + value;  // Changed from $
                                }
                            }
                        },
                        x: {
                            title: {
                                display: true,
                                text: 'Hour of Day'
                            },
                            ticks: {
                                autoSkip: false,
                                maxRotation: 45,
                                minRotation: 45
                            }
                        }
                    }
                }
            });
        }
    }
    
    async refresh_dashboard() {
        this.show_notification('Refreshing dashboard...', 'info');
        await this.fetch_data_with_filter();
        await this.fetch_additional_data();
        await this.render_all_charts();
        this.show_notification('Dashboard refreshed successfully!', 'success');
    }
    
    async open_target_settings() {
        const currentTarget = this.state.sales_target.target_amount || 0;
        const newTarget = prompt('Enter new monthly sales target:', currentTarget);
        
        if (newTarget !== null && newTarget !== '') {
            const targetValue = parseFloat(newTarget);
            if (!isNaN(targetValue) && targetValue >= 0) {
                try {
                    const result = await this.orm.call('pos.order', 'update_target', [{
                        target_amount: targetValue
                    }]);
                    
                    if (result.success) {
                        this.show_notification(result.message, 'success');
                        const targetData = await this.orm.call('pos.order', 'get_sales_target_data', []);
                        this.state.sales_target = targetData;
                        await this.render_target_chart();
                    }
                } catch (error) {
                    console.error('Error updating target:', error);
                    this.show_notification('Error updating target', 'danger');
                }
            } else {
                this.show_notification('Please enter a valid positive number', 'warning');
            }
        }
    }
    
    async print_report() {
        try {
            // Create a simple print report
            const printWindow = window.open('', '_blank');
            printWindow.document.write(`
                <html>
                <head>
                    <title>POS Dashboard Report</title>
                    <style>
                        body { font-family: Arial, sans-serif; margin: 20px; }
                        .header { text-align: center; margin-bottom: 30px; }
                        .section { margin-bottom: 20px; }
                        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
                        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                        th { background-color: #f2f2f2; }
                        @media print {
                            body { margin: 0; }
                            .no-print { display: none; }
                        }
                    </style>
                </head>
                <body>
                    <div class="header">
                        <h1>POS Dashboard Report</h1>
                        <p>Generated: ${new Date().toLocaleString()}</p>
                    </div>
                    
                    <div class="section">
                        <h2>Sales Summary</h2>
                        <table>
                            <tr>
                                <th>Metric</th>
                                <th>Value</th>
                            </tr>
                            <tr>
                                <td>Total Sales</td>
                                <td>${this.state.total_sale}</td>
                            </tr>
                            <tr>
                                <td>Total Orders</td>
                                <td>${this.state.total_order_count}</td>
                            </tr>
                            <tr>
                                <td>Today's Orders</td>
                                <td>${this.state.today_sale}</td>
                            </tr>
                            <tr>
                                <td>Active Sessions</td>
                                <td>${this.state.total_session}</td>
                            </tr>
                        </table>
                    </div>
                    
                    <div class="section no-print">
                        <button onclick="window.print()">Print Report</button>
                        <button onclick="window.close()">Close</button>
                    </div>
                </body>
                </html>
            `);
            printWindow.document.close();
            
            this.show_notification('Report generated successfully', 'success');
        } catch (error) {
            console.error('Error generating report:', error);
            this.show_notification('Error generating report', 'danger');
        }
    }
    
    view_customer_details = (customerId) => {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: 'res.partner',
            res_id: customerId,
            views: [[false, 'form']],
            target: 'current'
        });
    };
    
    show_notification(message, type = 'info') {
        this.notification.add(message, {
            type: type,
            title: 'POS Dashboard'
        });
    }
    
    // Original methods for card clicks
    pos_order_today(e) {
        var self = this;
        var date = new Date();
        var yesterday = new Date(date.getTime());
        yesterday.setDate(date.getDate() - 1);
        e.stopPropagation();
        e.preventDefault();
        this.user.hasGroup('point_of_sale.group_pos_manager').then(function(has_group) {
            if(has_group) {
                self.actionService.doAction({
                    name: _t("Today Order"),
                    type: 'ir.actions.act_window',
                    res_model: 'pos.order',
                    view_mode: 'tree,form',
                    views: [[false, 'list'],[false, 'form']],
                    domain: [['date_order','<=', date],['date_order', '>=', yesterday]],
                    target: 'current'
                })
            }
        });
    }
    
    pos_refund_orders(e) {
        var self = this;
        e.stopPropagation();
        e.preventDefault();
        this.user.hasGroup('point_of_sale.group_pos_manager').then(function(has_group) {
            if(has_group) {
                self.actionService.doAction({
                    name: _t("Refund Orders"),
                    type: 'ir.actions.act_window',
                    res_model: 'pos.order',
                    view_mode: 'tree,form',
                    views: [[false, 'list'],[false, 'form']],
                    domain: [['amount_total', '<', 0.0]],
                    target: 'current'
                })
            }
        });
    }
    
    pos_refund_today_orders(e) {
        var self = this;
        var date = new Date();
        var yesterday = new Date(date.getTime());
        yesterday.setDate(date.getDate() - 1);
        e.stopPropagation();
        e.preventDefault();
        this.user.hasGroup('point_of_sale.group_pos_manager').then(function(has_group) {
            if(has_group) {
                self.actionService.doAction({
                    name: _t("Refund Orders"),
                    type: 'ir.actions.act_window',
                    res_model: 'pos.order',
                    view_mode: 'tree,form',
                    views: [[false, 'list'],[false, 'form']],
                    domain: [['amount_total', '<', 0.0],['date_order','<=', date],['date_order', '>=', yesterday]],
                    target: 'current'
                })
            }
        });
    }
    
    pos_order(e) {
        var self = this;
        e.stopPropagation();
        e.preventDefault();
        this.user.hasGroup('point_of_sale.group_pos_manager').then(function(has_group) {
            if(has_group) {
                self.actionService.doAction({
                    name: _t("Total Order"),
                    type: 'ir.actions.act_window',
                    res_model: 'pos.order',
                    view_mode: 'tree,form',
                    views: [[false, 'list'],[false, 'form']],
                    target: 'current'
                })
            }
        });
    }
    
    pos_session(e) {
        var self = this;
        e.stopPropagation();
        e.preventDefault();
        this.user.hasGroup('point_of_sale.group_pos_manager').then(function(has_group) {
            if(has_group) {
                self.actionService.doAction({
                    name: _t("sessions"),
                    type: 'ir.actions.act_window',
                    res_model: 'pos.session',
                    view_mode: 'tree,form',
                    views: [[false, 'list'],[false, 'form']],
                    target: 'current'
                })
            }
        });
    }
    
    onclick_pos_sales(events) {
        var option = typeof events === 'string' ? events : events.target.value;
        this.render_sales_chart(option);
    }
}

PosDashboard.template = 'PosDashboard';
registry.category("actions").add("pos_order_menu", PosDashboard);