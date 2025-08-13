/**
 * Utilities Tracker Frontend Application
 * 
 * JavaScript application for the Utilities Tracker dashboard.
 * Handles API communication, data visualization, and user interactions.
 */

// Configuration
const CONFIG = {
    API_BASE_URL: 'http://localhost:5000/api',
    CHART_COLORS: {
        primary: '#0d6efd',
        success: '#198754',
        info: '#0dcaf0',
        warning: '#ffc107',
        danger: '#dc3545',
        electricity: '#ffc107',
        gas: '#fd7e14',
        water: '#20c997'
    },
    DATE_FORMAT: {
        locale: 'en-US',
        options: { year: 'numeric', month: 'short', day: 'numeric' }
    }
};

// Global state
let currentPage = 1;
let currentFilters = {};
let charts = {};

/**
 * Initialize the application
 */
$(document).ready(function() {
    console.log('Initializing Utilities Tracker Dashboard...');
    
    // Check system health
    checkSystemHealth();
    
    // Load dashboard data
    loadDashboard();
    
    // Set up event listeners
    setupEventListeners();
    
    // Load initial section
    showSection('dashboard');
});

/**
 * Set up event listeners
 */
function setupEventListeners() {
    // Filter change events
    $('#providerFilter, #serviceFilter, #startDateFilter, #endDateFilter').on('change', function() {
        if (getCurrentSection() === 'invoices') {
            applyFilters();
        }
    });
    
    // Enter key for filters
    $('#startDateFilter, #endDateFilter').on('keypress', function(e) {
        if (e.which === 13) {
            applyFilters();
        }
    });
}

/**
 * Show/hide content sections
 */
function showSection(sectionId) {
    // Hide all sections
    $('.content-section').hide();
    
    // Show selected section
    $(`#${sectionId}`).show();
    
    // Update navigation
    $('.navbar-nav .nav-link').removeClass('active');
    $(`.navbar-nav .nav-link[href="#${sectionId}"]`).addClass('active');
    
    // Load section-specific data
    switch(sectionId) {
        case 'dashboard':
            loadDashboard();
            break;
        case 'invoices':
            loadInvoices();
            break;
        case 'analytics':
            loadAnalytics();
            break;
    }
}

/**
 * Get current active section
 */
function getCurrentSection() {
    return $('.content-section:visible').attr('id');
}

/**
 * Check system health
 */
async function checkSystemHealth() {
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/health`);
        const health = await response.json();
        
        // Update environment info
        $('#environment').text(health.environment === 'aws' ? 'AWS' : 'Local');
        
        // Update status badge
        const statusBadge = $('#systemStatus');
        if (health.status === 'healthy') {
            statusBadge.removeClass('bg-danger bg-warning').addClass('bg-success').text('Healthy');
        } else {
            statusBadge.removeClass('bg-success bg-warning').addClass('bg-danger').text('Error');
        }
        
        console.log('System health check:', health);
        
    } catch (error) {
        console.error('Health check failed:', error);
        $('#systemStatus').removeClass('bg-success bg-warning').addClass('bg-danger').text('Offline');
    }
}

/**
 * Load dashboard data and visualizations
 */
async function loadDashboard() {
    showLoading();
    
    try {
        // Load analytics data
        const analytics = await apiCall('/analytics');
        
        // Update KPI cards
        updateKPICards(analytics.overview);
        
        // Load recent invoices
        const invoices = await apiCall('/invoices?per_page=5');
        updateRecentInvoices(invoices.invoices);
        
        // Create charts
        createTrendsChart(analytics.monthly_trends);
        createServiceChart(analytics.service_breakdown);
        
    } catch (error) {
        console.error('Error loading dashboard:', error);
        showAlert('Error loading dashboard data', 'danger');
    } finally {
        hideLoading();
    }
}

/**
 * Update KPI cards with analytics data
 */
function updateKPICards(overview) {
    $('#totalInvoices').text(overview.total_invoices.toLocaleString());
    $('#totalAmount').text('$' + overview.total_amount.toLocaleString());
    $('#avgAmount').text('$' + overview.average_amount.toLocaleString());
    
    // Calculate this month's total (placeholder - would need actual current month data)
    const thisMonth = overview.total_amount * 0.08; // Approximate
    $('#thisMonth').text('$' + thisMonth.toLocaleString());
}

/**
 * Update recent invoices table
 */
function updateRecentInvoices(invoices) {
    const tableHtml = `
        <table class="table table-hover">
            <thead>
                <tr>
                    <th>Date</th>
                    <th>Provider</th>
                    <th>Service</th>
                    <th>Amount</th>
                    <th>Usage</th>
                </tr>
            </thead>
            <tbody>
                ${invoices.map(invoice => `
                    <tr>
                        <td>${formatDate(invoice.invoice_date)}</td>
                        <td><span class="text-provider">${invoice.provider_name}</span></td>
                        <td><span class="badge service-${invoice.service_type.toLowerCase()}">${invoice.service_type}</span></td>
                        <td class="text-currency">$${invoice.total_amount.toFixed(2)}</td>
                        <td>${invoice.usage_quantity ? invoice.usage_quantity.toFixed(1) : 'N/A'}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
    
    $('#recentInvoices').html(tableHtml);
}

/**
 * Load invoices with filters and pagination
 */
async function loadInvoices(page = 1) {
    showLoading();
    
    try {
        // Build query parameters
        const params = new URLSearchParams({
            page: page,
            per_page: 20,
            ...currentFilters
        });
        
        const data = await apiCall(`/invoices?${params}`);
        
        // Update invoices table
        updateInvoicesTable(data.invoices);
        
        // Update pagination
        updatePagination(data.pagination);
        
        // Load providers for filter dropdown
        if (page === 1) {
            loadProviders();
        }
        
        currentPage = page;
        
    } catch (error) {
        console.error('Error loading invoices:', error);
        showAlert('Error loading invoices', 'danger');
    } finally {
        hideLoading();
    }
}

/**
 * Update invoices table
 */
function updateInvoicesTable(invoices) {
    const tableHtml = `
        <table class="table table-hover">
            <thead>
                <tr>
                    <th>Date</th>
                    <th>Provider</th>
                    <th>Service</th>
                    <th>Amount</th>
                    <th>Usage</th>
                    <th>Rate</th>
                    <th>Period</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                ${invoices.length > 0 ? invoices.map(invoice => `
                    <tr>
                        <td>${formatDate(invoice.invoice_date)}</td>
                        <td><span class="text-provider">${invoice.provider_name}</span></td>
                        <td><span class="badge service-${invoice.service_type.toLowerCase()}">${invoice.service_type}</span></td>
                        <td class="text-currency">$${invoice.total_amount.toFixed(2)}</td>
                        <td>${invoice.usage_quantity ? invoice.usage_quantity.toFixed(1) : 'N/A'}</td>
                        <td>${invoice.usage_rate ? '$' + invoice.usage_rate.toFixed(4) : 'N/A'}</td>
                        <td class="small">
                            ${invoice.billing_period_start ? formatDate(invoice.billing_period_start) : 'N/A'} -
                            ${invoice.billing_period_end ? formatDate(invoice.billing_period_end) : 'N/A'}
                        </td>
                        <td><span class="badge status-${invoice.processing_status}">${invoice.processing_status}</span></td>
                    </tr>
                `).join('') : `
                    <tr>
                        <td colspan="8" class="text-center py-4">
                            <i class="bi bi-inbox fs-1 text-muted"></i>
                            <p class="mt-2 text-muted">No invoices found</p>
                        </td>
                    </tr>
                `}
            </tbody>
        </table>
    `;
    
    $('#invoicesTable').html(tableHtml);
}

/**
 * Update pagination controls
 */
function updatePagination(pagination) {
    if (pagination.pages <= 1) {
        $('#pagination').hide();
        return;
    }
    
    $('#pagination').show();
    
    const paginationHtml = `
        <ul class="pagination justify-content-center">
            <li class="page-item ${pagination.page === 1 ? 'disabled' : ''}">
                <a class="page-link" href="#" onclick="loadInvoices(${pagination.page - 1})">Previous</a>
            </li>
            ${Array.from({length: pagination.pages}, (_, i) => i + 1).map(page => `
                <li class="page-item ${page === pagination.page ? 'active' : ''}">
                    <a class="page-link" href="#" onclick="loadInvoices(${page})">${page}</a>
                </li>
            `).join('')}
            <li class="page-item ${pagination.page === pagination.pages ? 'disabled' : ''}">
                <a class="page-link" href="#" onclick="loadInvoices(${pagination.page + 1})">Next</a>
            </li>
        </ul>
    `;
    
    $('#pagination').html(paginationHtml);
}

/**
 * Load providers for filter dropdown
 */
async function loadProviders() {
    try {
        const data = await apiCall('/providers');
        
        const providerOptions = data.providers.map(provider => 
            `<option value="${provider.provider_name}">${provider.provider_name}</option>`
        ).join('');
        
        $('#providerFilter').html('<option value="">All Providers</option>' + providerOptions);
        
    } catch (error) {
        console.error('Error loading providers:', error);
    }
}

/**
 * Load analytics section
 */
async function loadAnalytics() {
    showLoading();
    
    try {
        const analytics = await apiCall('/analytics');
        const providers = await apiCall('/providers');
        
        // Create detailed charts
        createMonthlyChart(analytics.monthly_trends);
        createProviderChart(analytics.provider_performance);
        
        // Update provider statistics table
        updateProviderStats(providers.providers);
        
    } catch (error) {
        console.error('Error loading analytics:', error);
        showAlert('Error loading analytics data', 'danger');
    } finally {
        hideLoading();
    }
}

/**
 * Update provider statistics table
 */
function updateProviderStats(providers) {
    const tableHtml = `
        <table class="table table-striped">
            <thead>
                <tr>
                    <th>Provider</th>
                    <th>Service Type</th>
                    <th>Invoices</th>
                    <th>Total Amount</th>
                    <th>Average Amount</th>
                    <th>Latest Invoice</th>
                </tr>
            </thead>
            <tbody>
                ${providers.map(provider => `
                    <tr>
                        <td><span class="text-provider">${provider.provider_name}</span></td>
                        <td><span class="badge service-${provider.service_type.toLowerCase()}">${provider.service_type}</span></td>
                        <td>${provider.invoice_count}</td>
                        <td class="text-currency">$${provider.total_amount.toFixed(2)}</td>
                        <td class="text-currency">$${provider.avg_amount.toFixed(2)}</td>
                        <td>${formatDate(provider.latest_invoice)}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
    
    $('#providerStats').html(tableHtml);
}

/**
 * Apply invoice filters
 */
function applyFilters() {
    currentFilters = {};
    
    const provider = $('#providerFilter').val();
    const serviceType = $('#serviceFilter').val();
    const startDate = $('#startDateFilter').val();
    const endDate = $('#endDateFilter').val();
    
    if (provider) currentFilters.provider = provider;
    if (serviceType) currentFilters.service_type = serviceType;
    if (startDate) currentFilters.start_date = startDate;
    if (endDate) currentFilters.end_date = endDate;
    
    loadInvoices(1);
}

/**
 * Clear all filters
 */
function clearFilters() {
    $('#providerFilter, #serviceFilter').val('');
    $('#startDateFilter, #endDateFilter').val('');
    currentFilters = {};
    loadInvoices(1);
}

/**
 * Trigger manual sync
 */
async function triggerSync() {
    try {
        showAlert('Initiating sync process...', 'info');
        
        const result = await apiCall('/sync', 'POST', {
            mode: 'incremental'
        });
        
        showAlert(result.message, 'success');
        
        // Refresh dashboard after sync
        setTimeout(() => {
            if (getCurrentSection() === 'dashboard') {
                loadDashboard();
            }
        }, 2000);
        
    } catch (error) {
        console.error('Sync error:', error);
        showAlert('Failed to initiate sync process', 'danger');
    }
}

/**
 * Export data as CSV
 */
async function exportData() {
    try {
        showAlert('Generating CSV export...', 'info');
        
        const result = await apiCall('/export/csv');
        
        // Create and download CSV file
        const blob = new Blob([result.csv_data], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `utilities-tracker-export-${new Date().toISOString().split('T')[0]}.csv`;
        a.click();
        window.URL.revokeObjectURL(url);
        
        showAlert(`CSV exported successfully (${result.record_count} records)`, 'success');
        
    } catch (error) {
        console.error('Export error:', error);
        showAlert('Failed to export data', 'danger');
    }
}

/**
 * Show system health modal
 */
async function showHealth() {
    try {
        const health = await apiCall('/health');
        
        const healthHtml = `
            <div class="modal fade" id="healthModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title"><i class="bi bi-heart-pulse"></i> System Health</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="row">
                                <div class="col-sm-4"><strong>Status:</strong></div>
                                <div class="col-sm-8">
                                    <span class="badge ${health.status === 'healthy' ? 'bg-success' : 'bg-danger'}">
                                        ${health.status}
                                    </span>
                                </div>
                            </div>
                            <div class="row mt-2">
                                <div class="col-sm-4"><strong>Environment:</strong></div>
                                <div class="col-sm-8">${health.environment}</div>
                            </div>
                            <div class="row mt-2">
                                <div class="col-sm-4"><strong>Database:</strong></div>
                                <div class="col-sm-8">${health.database.database_type}</div>
                            </div>
                            <div class="row mt-2">
                                <div class="col-sm-4"><strong>Invoice Count:</strong></div>
                                <div class="col-sm-8">${health.database.invoice_count}</div>
                            </div>
                            <div class="row mt-2">
                                <div class="col-sm-4"><strong>Last Updated:</strong></div>
                                <div class="col-sm-8">${formatDate(health.timestamp)}</div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Remove existing modal and add new one
        $('#healthModal').remove();
        $('body').append(healthHtml);
        
        // Show modal
        new bootstrap.Modal(document.getElementById('healthModal')).show();
        
    } catch (error) {
        console.error('Health check error:', error);
        showAlert('Failed to get system health', 'danger');
    }
}

/**
 * Create trends chart for dashboard
 */
function createTrendsChart(monthlyData) {
    const ctx = document.getElementById('trendsChart').getContext('2d');
    
    // Destroy existing chart if it exists
    if (charts.trendsChart) {
        charts.trendsChart.destroy();
    }
    
    charts.trendsChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: monthlyData.map(d => d.month),
            datasets: [{
                label: 'Monthly Spending',
                data: monthlyData.map(d => d.total_amount),
                borderColor: CONFIG.CHART_COLORS.primary,
                backgroundColor: CONFIG.CHART_COLORS.primary + '20',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return '$' + value.toLocaleString();
                        }
                    }
                }
            }
        }
    });
}

/**
 * Create service breakdown chart
 */
function createServiceChart(serviceData) {
    const ctx = document.getElementById('serviceChart').getContext('2d');
    
    if (charts.serviceChart) {
        charts.serviceChart.destroy();
    }
    
    charts.serviceChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: serviceData.map(d => d.service_type),
            datasets: [{
                data: serviceData.map(d => d.total),
                backgroundColor: [
                    CONFIG.CHART_COLORS.electricity,
                    CONFIG.CHART_COLORS.gas,
                    CONFIG.CHART_COLORS.water
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

/**
 * Create monthly spending chart for analytics
 */
function createMonthlyChart(monthlyData) {
    const ctx = document.getElementById('monthlyChart').getContext('2d');
    
    if (charts.monthlyChart) {
        charts.monthlyChart.destroy();
    }
    
    charts.monthlyChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: monthlyData.map(d => d.month),
            datasets: [{
                label: 'Monthly Total',
                data: monthlyData.map(d => d.total_amount),
                backgroundColor: CONFIG.CHART_COLORS.primary + '80',
                borderColor: CONFIG.CHART_COLORS.primary,
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return '$' + value.toLocaleString();
                        }
                    }
                }
            }
        }
    });
}

/**
 * Create provider comparison chart
 */
function createProviderChart(providerData) {
    const ctx = document.getElementById('providerChart').getContext('2d');
    
    if (charts.providerChart) {
        charts.providerChart.destroy();
    }
    
    charts.providerChart = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: providerData.map(d => d.provider_name),
            datasets: [{
                data: providerData.map(d => d.total),
                backgroundColor: [
                    CONFIG.CHART_COLORS.primary,
                    CONFIG.CHART_COLORS.success,
                    CONFIG.CHART_COLORS.warning,
                    CONFIG.CHART_COLORS.info,
                    CONFIG.CHART_COLORS.danger
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

/**
 * Utility function for API calls
 */
async function apiCall(endpoint, method = 'GET', data = null) {
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json'
        }
    };
    
    if (data) {
        options.body = JSON.stringify(data);
    }
    
    const response = await fetch(`${CONFIG.API_BASE_URL}${endpoint}`, options);
    
    if (!response.ok) {
        throw new Error(`API call failed: ${response.status} ${response.statusText}`);
    }
    
    return response.json();
}

/**
 * Show loading spinner
 */
function showLoading() {
    $('#loading').show();
}

/**
 * Hide loading spinner
 */
function hideLoading() {
    $('#loading').hide();
}

/**
 * Show alert message
 */
function showAlert(message, type = 'info', duration = 5000) {
    const alertHtml = `
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    $('#alertContainer').html(alertHtml);
    
    // Auto-hide after duration
    if (duration > 0) {
        setTimeout(() => {
            $('.alert').alert('close');
        }, duration);
    }
}

/**
 * Format date for display
 */
function formatDate(dateString) {
    if (!dateString) return 'N/A';
    
    const date = new Date(dateString);
    return date.toLocaleDateString(CONFIG.DATE_FORMAT.locale, CONFIG.DATE_FORMAT.options);
}