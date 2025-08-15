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
        case 'configuration':
            loadGmailConfiguration();
            loadEmailCaptureConfiguration();
            loadUtilityAttributes();
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
    
    // Display total service charges
    const serviceCharges = overview.total_service_charges || 0;
    $('#totalServiceCharges').text('$' + serviceCharges.toLocaleString());
    
    // Display total usage charges
    const usageCharges = overview.total_usage_charges || 0;
    $('#totalUsageCharges').text('$' + usageCharges.toLocaleString());
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
                    <th>Service Charge</th>
                    <th>Usage Charge</th>
                    <th>Usage</th>
                    <th>Rate</th>
                </tr>
            </thead>
            <tbody>
                ${invoices.map(invoice => {
                    const usageCharge = (invoice.usage_quantity && invoice.usage_rate) 
                        ? (parseFloat(invoice.usage_quantity) * parseFloat(invoice.usage_rate))
                        : 0;
                    
                    return `
                        <tr>
                            <td>${formatDate(invoice.invoice_date)}</td>
                            <td><span class="text-provider">${invoice.provider_name}</span></td>
                            <td><span class="badge service-${invoice.service_type.toLowerCase()}">${invoice.service_type}</span></td>
                            <td class="text-currency">$${invoice.total_amount.toFixed(2)}</td>
                            <td class="text-currency">$${invoice.service_charge ? invoice.service_charge.toFixed(2) : '0.00'}</td>
                            <td class="text-currency">$${usageCharge.toFixed(2)}</td>
                            <td>${invoice.usage_quantity ? invoice.usage_quantity.toFixed(1) : 'N/A'}</td>
                            <td>${invoice.usage_rate ? '$' + invoice.usage_rate.toFixed(4) : 'N/A'}</td>
                        </tr>
                    `;
                }).join('')}
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
                    <th>Service Charge</th>
                    <th>Usage Charge</th>
                    <th>Usage</th>
                    <th>Rate</th>
                    <th>Period</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                ${invoices.length > 0 ? invoices.map(invoice => {
                    const usageCharge = (invoice.usage_quantity && invoice.usage_rate) 
                        ? (parseFloat(invoice.usage_quantity) * parseFloat(invoice.usage_rate))
                        : 0;
                    
                    return `
                        <tr>
                            <td>${formatDate(invoice.invoice_date)}</td>
                            <td><span class="text-provider">${invoice.provider_name}</span></td>
                            <td><span class="badge service-${invoice.service_type.toLowerCase()}">${invoice.service_type}</span></td>
                            <td class="text-currency">$${invoice.total_amount.toFixed(2)}</td>
                            <td class="text-currency">$${invoice.service_charge ? invoice.service_charge.toFixed(2) : '0.00'}</td>
                            <td class="text-currency">$${usageCharge.toFixed(2)}</td>
                            <td>${invoice.usage_quantity ? invoice.usage_quantity.toFixed(1) : 'N/A'}</td>
                            <td>${invoice.usage_rate ? '$' + invoice.usage_rate.toFixed(4) : 'N/A'}</td>
                            <td class="small">
                                ${invoice.billing_period_start ? formatDate(invoice.billing_period_start) : 'N/A'} -
                                ${invoice.billing_period_end ? formatDate(invoice.billing_period_end) : 'N/A'}
                            </td>
                            <td><span class="badge status-${invoice.processing_status}">${invoice.processing_status}</span></td>
                        </tr>
                    `;
                }).join('') : `
                    <tr>
                        <td colspan="10" class="text-center py-4">
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
        // Load both basic and enhanced analytics
        const analytics = await apiCall('/analytics');
        const providers = await apiCall('/providers');
        
        // Load enhanced analytics with current filter values
        await updateAnalytics();
        
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
 * Update analytics based on current filter selections
 */
async function updateAnalytics() {
    try {
        const serviceType = document.getElementById('analyticsServiceFilter').value;
        const months = document.getElementById('analyticsTimeFilter').value;
        const analysisType = document.getElementById('analyticsTypeFilter').value;
        
        // Build query parameters
        const params = new URLSearchParams();
        if (serviceType) params.append('service_type', serviceType);
        params.append('months', months);
        params.append('analysis_type', analysisType);
        
        // Fetch enhanced analytics data
        const enhancedAnalytics = await apiCall(`/analytics/enhanced?${params.toString()}`);
        
        // Store globally for chart type changes
        window.currentAnalyticsData = enhancedAnalytics;
        
        // Update main chart title
        const serviceText = serviceType ? serviceType : 'All Services';
        const typeText = {
            'spending': 'Spending',
            'usage': 'Usage',
            'rates': 'Rate',
            'service_fees': 'Service Fee'
        }[analysisType] || 'Spending';
        
        document.getElementById('mainChartTitle').innerHTML = 
            `<i class="bi bi-bar-chart-line"></i> Monthly ${typeText} Trends - ${serviceText}`;
        
        // Update all charts
        createMainAnalyticsChart(enhancedAnalytics, analysisType, serviceType);
        createServiceTrendCharts(enhancedAnalytics.service_trends, analysisType);
        createRateComparisonChart(enhancedAnalytics.rate_comparison);
        createServiceFeeChart(enhancedAnalytics.service_trends);
        updateServiceStats(enhancedAnalytics.service_statistics);
        updateCostBreakdown(enhancedAnalytics.cost_breakdown);
        
    } catch (error) {
        console.error('Error updating analytics:', error);
        showAlert('Error updating analytics data', 'danger');
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
 * Export invoices to CSV
 */
async function exportInvoicesCSV() {
    try {
        const exportBtn = $('button[onclick="exportInvoicesCSV()"]');
        const originalText = exportBtn.html();
        exportBtn.html('<i class="bi bi-hourglass-split"></i> Exporting...').prop('disabled', true);
        
        // Build query parameters for current filters
        const params = new URLSearchParams(currentFilters);
        params.append('export', 'true');
        
        // Make request to export endpoint
        const response = await fetch(`${CONFIG.API_BASE_URL}/export/csv?${params.toString()}`);
        
        if (!response.ok) {
            throw new Error(`Export failed: ${response.status} ${response.statusText}`);
        }
        
        // Get the CSV data
        const csvData = await response.text();
        
        // Create download link
        const blob = new Blob([csvData], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        
        if (link.download !== undefined) {
            const url = URL.createObjectURL(blob);
            link.setAttribute('href', url);
            
            // Generate filename with current date and filters
            const dateStr = new Date().toISOString().split('T')[0];
            let filename = `invoices_${dateStr}`;
            
            // Add filter info to filename
            if (currentFilters.service_type) {
                filename += `_${currentFilters.service_type.toLowerCase()}`;
            }
            if (currentFilters.provider) {
                filename += `_${currentFilters.provider.toLowerCase().replace(/\s+/g, '_')}`;
            }
            
            link.setAttribute('download', `${filename}.csv`);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            showAlert('CSV export completed successfully', 'success');
        } else {
            throw new Error('Browser does not support file downloads');
        }
        
    } catch (error) {
        console.error('CSV export failed:', error);
        showAlert(`CSV export failed: ${error.message}`, 'danger');
    } finally {
        const exportBtn = $('button[onclick="exportInvoicesCSV()"]');
        exportBtn.html('<i class="bi bi-download"></i> Export CSV').prop('disabled', false);
    }
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

// =============================================================================
// CONFIGURATION FUNCTIONS
// =============================================================================

/**
 * Load Gmail configuration when configuration section is shown
 */
function loadGmailConfiguration() {
    // Load current configuration
    fetch(`${CONFIG.API_BASE_URL}/configuration/gmail`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const config = data.config;
                $('#gmailClientId').val(config.client_id || '');
                $('#gmailClientSecret').val(config.client_secret ? '••••••••' : '');
                $('#gmailRefreshToken').val(config.refresh_token ? '••••••••' : '');
                
                updateGmailConnectionStatus(config.status);
            }
        })
        .catch(error => {
            console.error('Failed to load Gmail configuration:', error);
            showAlert('Failed to load Gmail configuration', 'danger');
        });

    // Load connection status
    loadConnectionStatus();
}

/**
 * Save Gmail configuration
 */
function saveGmailConfig() {
    const config = {
        client_id: $('#gmailClientId').val().trim(),
        client_secret: $('#gmailClientSecret').val().trim(),
        refresh_token: $('#gmailRefreshToken').val().trim()
    };

    // Validate required fields
    if (!config.client_id || !config.client_secret) {
        showAlert('Please fill in Client ID and Client Secret', 'warning');
        return;
    }

    // Show loading state
    const saveBtn = $('button[onclick="saveGmailConfig()"]');
    const originalText = saveBtn.html();
    saveBtn.html('<i class="bi bi-hourglass-split"></i> Saving...').prop('disabled', true);

    fetch(`${CONFIG.API_BASE_URL}/configuration/gmail`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(config)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('Gmail configuration saved successfully', 'success');
            updateGmailConnectionStatus('configured');
            loadConnectionStatus();
        } else {
            showAlert(`Failed to save configuration: ${data.error}`, 'danger');
        }
    })
    .catch(error => {
        console.error('Failed to save Gmail configuration:', error);
        showAlert('Failed to save Gmail configuration', 'danger');
    })
    .finally(() => {
        saveBtn.html(originalText).prop('disabled', false);
    });
}

/**
 * Test Gmail connection
 */
function testGmailConnection() {
    const testBtn = $('button[onclick="testGmailConnection()"]');
    const originalText = testBtn.html();
    testBtn.html('<i class="bi bi-hourglass-split"></i> Testing...').prop('disabled', true);

    fetch(`${CONFIG.API_BASE_URL}/configuration/gmail/test`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('Gmail connection test successful', 'success');
            updateGmailConnectionStatus('connected');
            loadConnectionStatus();
        } else {
            showAlert(`Connection test failed: ${data.error}`, 'danger');
            updateGmailConnectionStatus('failed');
        }
    })
    .catch(error => {
        console.error('Gmail connection test failed:', error);
        showAlert('Gmail connection test failed', 'danger');
        updateGmailConnectionStatus('failed');
    })
    .finally(() => {
        testBtn.html(originalText).prop('disabled', false);
    });
}

/**
 * Initiate OAuth2 flow
 */
function initiateOAuth() {
    const oauthBtn = $('button[onclick="initiateOAuth()"]');
    const originalText = oauthBtn.html();
    oauthBtn.html('<i class="bi bi-hourglass-split"></i> Starting...').prop('disabled', true);

    fetch(`${CONFIG.API_BASE_URL}/configuration/gmail/oauth-url`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success && data.auth_url) {
            // Open OAuth URL in new window
            const authWindow = window.open(data.auth_url, 'gmail_oauth', 'width=600,height=400');
            
            showAlert('OAuth2 flow initiated. Complete authentication in the popup window.', 'info');
            
            // Monitor for window closure (user completed OAuth)
            const checkClosed = setInterval(() => {
                if (authWindow.closed) {
                    clearInterval(checkClosed);
                    setTimeout(() => {
                        loadGmailConfiguration();
                        showAlert('Please test the connection to verify OAuth2 completion', 'info');
                    }, 1000);
                }
            }, 1000);
        } else {
            showAlert(`Failed to start OAuth2 flow: ${data.error}`, 'danger');
        }
    })
    .catch(error => {
        console.error('Failed to start OAuth2 flow:', error);
        showAlert('Failed to start OAuth2 flow', 'danger');
    })
    .finally(() => {
        oauthBtn.html(originalText).prop('disabled', false);
    });
}

/**
 * Update Gmail connection status badge
 */
function updateGmailConnectionStatus(status) {
    const statusBadge = $('#gmailConnectionStatus');
    
    switch (status) {
        case 'connected':
            statusBadge.removeClass().addClass('badge bg-success').text('Connected');
            break;
        case 'configured':
            statusBadge.removeClass().addClass('badge bg-info').text('Configured');
            break;
        case 'failed':
            statusBadge.removeClass().addClass('badge bg-danger').text('Failed');
            break;
        case 'not_configured':
            statusBadge.removeClass().addClass('badge bg-warning').text('Not Configured');
            break;
        default:
            statusBadge.removeClass().addClass('badge bg-secondary').text('Unknown');
    }
}

/**
 * Load detailed connection status
 */
function loadConnectionStatus() {
    fetch(`${CONFIG.API_BASE_URL}/configuration/status`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayConnectionStatus(data.status);
            }
        })
        .catch(error => {
            console.error('Failed to load connection status:', error);
            $('#connectionStatusDetails').html('<p class="text-danger">Failed to load status</p>');
        });
}

/**
 * Display connection status details
 */
function displayConnectionStatus(status) {
    const statusHtml = `
        <div class="row">
            <div class="col-md-6">
                <h6>Authentication Status</h6>
                <ul class="list-unstyled">
                    <li><i class="bi bi-circle-fill text-${status.authentication.gmail ? 'success' : 'danger'}"></i> Gmail: ${status.authentication.gmail ? 'Connected' : 'Not Connected'}</li>
                    <li><i class="bi bi-circle-fill text-${status.authentication.outlook ? 'success' : 'secondary'}"></i> Outlook: ${status.authentication.outlook ? 'Connected' : 'Not Configured'}</li>
                </ul>
            </div>
            <div class="col-md-6">
                <h6>Recent Activity</h6>
                <ul class="list-unstyled">
                    <li><strong>Last Fetch:</strong> ${status.recent_activity.last_fetch || 'Never'}</li>
                    <li><strong>Total Processed:</strong> ${status.recent_activity.total_processed || 0}</li>
                    <li><strong>Success Rate:</strong> ${status.recent_activity.successful || 0}/${status.recent_activity.total_processed || 0}</li>
                </ul>
            </div>
        </div>
        <div class="row mt-3">
            <div class="col">
                <h6>Storage Information</h6>
                <p><strong>Local Files:</strong> ${status.storage.local_files || 0} PDFs stored locally</p>
                <p><strong>AWS Mode:</strong> ${status.storage.aws_mode ? 'Enabled' : 'Disabled'}</p>
            </div>
        </div>
    `;
    
    $('#connectionStatusDetails').html(statusHtml);
}

// =============================================================================
// EMAIL CAPTURE CONFIGURATION FUNCTIONS
// =============================================================================

/**
 * Load email capture configuration when tab is shown
 */
function loadEmailCaptureConfiguration() {
    // Load current provider configurations
    fetch(`${CONFIG.API_BASE_URL}/configuration/providers`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const providers = data.providers;
                
                // Populate electricity provider
                const elecProvider = providers.find(p => p.service_type === 'Electricity');
                if (elecProvider) {
                    $('#elecProviderName').val(elecProvider.provider_name || '');
                    $('#elecEmailAddresses').val(elecProvider.email_patterns?.from?.join('\n') || '');
                    $('#elecSubjectKeywords').val(elecProvider.email_patterns?.subject_keywords?.join(', ') || '');
                    $('#elecExcludeKeywords').val(elecProvider.email_patterns?.exclude_keywords?.join(', ') || '');
                }
                
                // Populate gas provider
                const gasProvider = providers.find(p => p.service_type === 'Gas');
                if (gasProvider) {
                    $('#gasProviderName').val(gasProvider.provider_name || '');
                    $('#gasEmailAddresses').val(gasProvider.email_patterns?.from?.join('\n') || '');
                    $('#gasSubjectKeywords').val(gasProvider.email_patterns?.subject_keywords?.join(', ') || '');
                    $('#gasExcludeKeywords').val(gasProvider.email_patterns?.exclude_keywords?.join(', ') || '');
                }
                
                // Populate water provider
                const waterProvider = providers.find(p => p.service_type === 'Water');
                if (waterProvider) {
                    $('#waterProviderName').val(waterProvider.provider_name || '');
                    $('#waterEmailAddresses').val(waterProvider.email_patterns?.from?.join('\n') || '');
                    $('#waterSubjectKeywords').val(waterProvider.email_patterns?.subject_keywords?.join(', ') || '');
                    $('#waterExcludeKeywords').val(waterProvider.email_patterns?.exclude_keywords?.join(', ') || '');
                }
                
                // Load global settings
                if (data.global_settings) {
                    const searchConfig = data.global_settings.search_configuration || {};
                    $('#searchDateRange').val(searchConfig.date_range_days || 90);
                    $('#maxResults').val(searchConfig.max_results_per_provider || 50);
                    $('#searchFolders').val(searchConfig.search_in_folders?.join(', ') || 'INBOX, Bills, Utilities');
                }
            }
        })
        .catch(error => {
            console.error('Failed to load email capture configuration:', error);
            showAlert('Failed to load email capture configuration', 'danger');
        });
}

/**
 * Save email capture configuration
 */
function saveEmailCaptureConfig() {
    const config = {
        providers: [
            {
                service_type: 'Electricity',
                provider_name: $('#elecProviderName').val().trim(),
                email_patterns: {
                    from: $('#elecEmailAddresses').val().split('\n').map(email => email.trim()).filter(email => email),
                    subject_keywords: $('#elecSubjectKeywords').val().split(',').map(keyword => keyword.trim()).filter(keyword => keyword),
                    exclude_keywords: $('#elecExcludeKeywords').val().split(',').map(keyword => keyword.trim()).filter(keyword => keyword),
                    attachment_types: ['.pdf']
                }
            },
            {
                service_type: 'Gas',
                provider_name: $('#gasProviderName').val().trim(),
                email_patterns: {
                    from: $('#gasEmailAddresses').val().split('\n').map(email => email.trim()).filter(email => email),
                    subject_keywords: $('#gasSubjectKeywords').val().split(',').map(keyword => keyword.trim()).filter(keyword => keyword),
                    exclude_keywords: $('#gasExcludeKeywords').val().split(',').map(keyword => keyword.trim()).filter(keyword => keyword),
                    attachment_types: ['.pdf']
                }
            },
            {
                service_type: 'Water',
                provider_name: $('#waterProviderName').val().trim(),
                email_patterns: {
                    from: $('#waterEmailAddresses').val().split('\n').map(email => email.trim()).filter(email => email),
                    subject_keywords: $('#waterSubjectKeywords').val().split(',').map(keyword => keyword.trim()).filter(keyword => keyword),
                    exclude_keywords: $('#waterExcludeKeywords').val().split(',').map(keyword => keyword.trim()).filter(keyword => keyword),
                    attachment_types: ['.pdf']
                }
            }
        ],
        global_settings: {
            search_configuration: {
                date_range_days: parseInt($('#searchDateRange').val()) || 90,
                max_results_per_provider: parseInt($('#maxResults').val()) || 50,
                search_in_folders: $('#searchFolders').val().split(',').map(folder => folder.trim()).filter(folder => folder)
            }
        }
    };

    // Validate required fields
    for (const provider of config.providers) {
        if (!provider.provider_name) {
            showAlert(`Please fill in the provider name for ${provider.service_type}`, 'warning');
            return;
        }
        if (provider.email_patterns.from.length === 0) {
            showAlert(`Please add at least one email address for ${provider.service_type}`, 'warning');
            return;
        }
    }

    // Show loading state
    const saveBtn = $('button[onclick="saveEmailCaptureConfig()"]');
    const originalText = saveBtn.html();
    saveBtn.html('<i class="bi bi-hourglass-split"></i> Saving...').prop('disabled', true);

    fetch(`${CONFIG.API_BASE_URL}/configuration/providers`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(config)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('Email capture configuration saved successfully', 'success');
        } else {
            showAlert(`Failed to save configuration: ${data.error}`, 'danger');
        }
    })
    .catch(error => {
        console.error('Failed to save email capture configuration:', error);
        showAlert('Failed to save email capture configuration', 'danger');
    })
    .finally(() => {
        saveBtn.html(originalText).prop('disabled', false);
    });
}

/**
 * Test email patterns by performing a dry run search
 */
function testEmailPatterns() {
    const testBtn = $('button[onclick="testEmailPatterns()"]');
    const originalText = testBtn.html();
    testBtn.html('<i class="bi bi-hourglass-split"></i> Testing...').prop('disabled', true);

    fetch(`${CONFIG.API_BASE_URL}/configuration/providers/test`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const results = data.results;
            let message = 'Email pattern test results:\n\n';
            
            for (const result of results) {
                message += `${result.service_type}: ${result.matches} potential matches found\n`;
                if (result.sample_subjects) {
                    message += `  Sample subjects: ${result.sample_subjects.join(', ')}\n`;
                }
            }
            
            showAlert(message, 'info', 10000); // Show for 10 seconds
        } else {
            showAlert(`Pattern test failed: ${data.error}`, 'danger');
        }
    })
    .catch(error => {
        console.error('Email pattern test failed:', error);
        showAlert('Email pattern test failed', 'danger');
    })
    .finally(() => {
        testBtn.html(originalText).prop('disabled', false);
    });
}

// ================================
// UTILITY ATTRIBUTES CONFIGURATION
// ================================

/**
 * Load utility attributes configuration when tab is shown
 */
function loadUtilityAttributes() {
    fetch(`${CONFIG.API_BASE_URL}/configuration/utility-attributes`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const attributes = data.attributes;
                
                // Load Electricity attributes
                if (attributes.electricity) {
                    $('#elecAttrProviderName').val(attributes.electricity.provider_name || '');
                    $('#elecBillingCycle').val(attributes.electricity.billing_cycle || 'monthly');
                    $('#elecCustomDays').val(attributes.electricity.custom_cycle_days || '');
                    $('#elecDueDate').val(attributes.electricity.due_date || '1');
                    $('#elecCustomDueDay').val(attributes.electricity.custom_due_day || '');
                    $('#elecAvgUsage').val(attributes.electricity.avg_monthly_usage || '');
                    
                    toggleCustomFields('elec', attributes.electricity.billing_cycle, attributes.electricity.due_date);
                }
                
                // Load Gas attributes
                if (attributes.gas) {
                    $('#gasAttrProviderName').val(attributes.gas.provider_name || '');
                    $('#gasBillingCycle').val(attributes.gas.billing_cycle || 'monthly');
                    $('#gasCustomDays').val(attributes.gas.custom_cycle_days || '');
                    $('#gasDueDate').val(attributes.gas.due_date || '1');
                    $('#gasCustomDueDay').val(attributes.gas.custom_due_day || '');
                    $('#gasAvgUsage').val(attributes.gas.avg_monthly_usage || '');
                    
                    toggleCustomFields('gas', attributes.gas.billing_cycle, attributes.gas.due_date);
                }
                
                // Load Water attributes
                if (attributes.water) {
                    $('#waterAttrProviderName').val(attributes.water.provider_name || '');
                    $('#waterBillingCycle').val(attributes.water.billing_cycle || 'quarterly');
                    $('#waterCustomDays').val(attributes.water.custom_cycle_days || '');
                    $('#waterDueDate').val(attributes.water.due_date || '1');
                    $('#waterCustomDueDay').val(attributes.water.custom_due_day || '');
                    $('#waterAvgUsage').val(attributes.water.avg_monthly_usage || '');
                    
                    toggleCustomFields('water', attributes.water.billing_cycle, attributes.water.due_date);
                }
                
                // Update billing schedule preview
                updateBillingSchedulePreview(attributes);
                
            }
        })
        .catch(error => {
            console.error('Failed to load utility attributes:', error);
            showAlert('Failed to load utility attributes configuration', 'warning');
        });
}

/**
 * Save utility attributes configuration
 */
function saveUtilityAttributes() {
    const attributes = {
        electricity: {
            provider_name: $('#elecAttrProviderName').val().trim(),
            billing_cycle: $('#elecBillingCycle').val(),
            custom_cycle_days: $('#elecBillingCycle').val() === 'custom' ? parseInt($('#elecCustomDays').val()) : null,
            due_date: $('#elecDueDate').val(),
            custom_due_day: $('#elecDueDate').val() === 'custom' ? parseInt($('#elecCustomDueDay').val()) : null,
            avg_monthly_usage: parseFloat($('#elecAvgUsage').val()) || null
        },
        gas: {
            provider_name: $('#gasAttrProviderName').val().trim(),
            billing_cycle: $('#gasBillingCycle').val(),
            custom_cycle_days: $('#gasBillingCycle').val() === 'custom' ? parseInt($('#gasCustomDays').val()) : null,
            due_date: $('#gasDueDate').val(),
            custom_due_day: $('#gasDueDate').val() === 'custom' ? parseInt($('#gasCustomDueDay').val()) : null,
            avg_monthly_usage: parseFloat($('#gasAvgUsage').val()) || null
        },
        water: {
            provider_name: $('#waterAttrProviderName').val().trim(),
            billing_cycle: $('#waterBillingCycle').val(),
            custom_cycle_days: $('#waterBillingCycle').val() === 'custom' ? parseInt($('#waterCustomDays').val()) : null,
            due_date: $('#waterDueDate').val(),
            custom_due_day: $('#waterDueDate').val() === 'custom' ? parseInt($('#waterCustomDueDay').val()) : null,
            avg_monthly_usage: parseFloat($('#waterAvgUsage').val()) || null
        }
    };

    // Show loading state
    const saveBtn = $('button[onclick="saveUtilityAttributes()"]');
    const originalText = saveBtn.html();
    saveBtn.html('<i class="bi bi-hourglass-split"></i> Saving...').prop('disabled', true);

    fetch(`${CONFIG.API_BASE_URL}/configuration/utility-attributes`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ attributes: attributes })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('Utility attributes saved successfully', 'success');
            updateBillingSchedulePreview(attributes);
        } else {
            showAlert(`Failed to save attributes: ${data.error}`, 'danger');
        }
    })
    .catch(error => {
        console.error('Failed to save utility attributes:', error);
        showAlert('Failed to save utility attributes', 'danger');
    })
    .finally(() => {
        saveBtn.html(originalText).prop('disabled', false);
    });
}

/**
 * Validate billing schedule and show any conflicts
 */
function validateBillingSchedule() {
    const validateBtn = $('button[onclick="validateBillingSchedule()"]');
    const originalText = validateBtn.html();
    validateBtn.html('<i class="bi bi-hourglass-split"></i> Validating...').prop('disabled', true);

    fetch(`${CONFIG.API_BASE_URL}/configuration/utility-attributes/validate`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const validation = data.validation;
            let message = 'Billing schedule validation:\n\n';
            
            if (validation.conflicts && validation.conflicts.length > 0) {
                message += 'Potential conflicts found:\n';
                validation.conflicts.forEach(conflict => {
                    message += `• ${conflict}\n`;
                });
                showAlert(message, 'warning', 8000);
            } else {
                message += 'No scheduling conflicts detected.\n';
                message += `Next expected bills:\n`;
                if (validation.next_bills) {
                    validation.next_bills.forEach(bill => {
                        message += `• ${bill.service}: ${bill.date}\n`;
                    });
                }
                showAlert(message, 'success', 6000);
            }
        } else {
            showAlert(`Validation failed: ${data.error}`, 'danger');
        }
    })
    .catch(error => {
        console.error('Billing schedule validation failed:', error);
        showAlert('Billing schedule validation failed', 'danger');
    })
    .finally(() => {
        validateBtn.html(originalText).prop('disabled', false);
    });
}

/**
 * Toggle custom fields based on dropdown selection
 */
function toggleCustomFields(prefix, billingCycle, dueDate) {
    // Toggle custom cycle days
    const customCycleDays = $(`#${prefix}CustomCycleDays`);
    if (billingCycle === 'custom') {
        customCycleDays.show();
    } else {
        customCycleDays.hide();
    }
    
    // Toggle custom due date
    const customDueDate = $(`#${prefix}CustomDueDate`);
    if (dueDate === 'custom') {
        customDueDate.show();
    } else {
        customDueDate.hide();
    }
}

/**
 * Update billing schedule preview table
 */
function updateBillingSchedulePreview(attributes) {
    if (!attributes || Object.keys(attributes).length === 0) {
        $('#billingSchedulePreview').html('<p class="text-muted">Configure utility attributes above to see billing schedule preview</p>');
        return;
    }

    // Calculate next 6 months of expected bills
    const today = new Date();
    const months = [];
    
    for (let i = 0; i < 6; i++) {
        const date = new Date(today.getFullYear(), today.getMonth() + i, 1);
        months.push(date);
    }

    let scheduleHtml = `
        <table class="table table-sm">
            <thead>
                <tr>
                    <th>Month</th>
                    <th>Electricity</th>
                    <th>Gas</th>
                    <th>Water</th>
                </tr>
            </thead>
            <tbody>`;

    months.forEach(month => {
        const monthStr = month.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
        
        // Calculate if bills are due this month for each service
        const elecDue = calculateBillDue('electricity', attributes.electricity, month);
        const gasDue = calculateBillDue('gas', attributes.gas, month);
        const waterDue = calculateBillDue('water', attributes.water, month);

        scheduleHtml += `
            <tr>
                <td><strong>${monthStr}</strong></td>
                <td>${elecDue ? '<span class="badge bg-warning text-dark">Due</span>' : '-'}</td>
                <td>${gasDue ? '<span class="badge bg-danger">Due</span>' : '-'}</td>
                <td>${waterDue ? '<span class="badge bg-primary">Due</span>' : '-'}</td>
            </tr>`;
    });

    scheduleHtml += '</tbody></table>';
    $('#billingSchedulePreview').html(scheduleHtml);
}

/**
 * Calculate if a bill is due in a given month
 */
function calculateBillDue(serviceType, attributes, month) {
    if (!attributes || !attributes.billing_cycle) {
        return false;
    }

    const cycleMonths = {
        'monthly': 1,
        'bi-monthly': 2,
        'quarterly': 3,
        'semi-annual': 6,
        'annual': 12
    };

    const cycle = cycleMonths[attributes.billing_cycle] || 1;
    
    // Simple calculation - in reality this would be more complex
    // This is just for preview purposes
    if (cycle === 1) return true; // Monthly - always due
    if (cycle === 2) return month.getMonth() % 2 === 0; // Bi-monthly - every other month
    if (cycle === 3) return month.getMonth() % 3 === 0; // Quarterly - every 3 months
    if (cycle === 6) return month.getMonth() % 6 === 0; // Semi-annual
    if (cycle === 12) return month.getMonth() === 0; // Annual - January
    
    return false;
}

// ================================
// ENHANCED ANALYTICS CHART FUNCTIONS  
// ================================

/**
 * Create main analytics chart based on analysis type
 */
function createMainAnalyticsChart(data, analysisType, serviceType) {
    const ctx = document.getElementById('mainAnalyticsChart');
    if (!ctx) return;
    
    // Destroy existing chart
    if (charts.mainAnalyticsChart) {
        charts.mainAnalyticsChart.destroy();
    }
    
    let chartData = {};
    let yAxisLabel = '';
    
    if (serviceType) {
        // Single service chart
        const serviceData = data.service_trends[serviceType];
        if (!serviceData || !serviceData[analysisType]) return;
        
        const trends = serviceData[analysisType];
        chartData = {
            labels: trends.map(t => t.month),
            datasets: [{
                label: getDatasetLabel(analysisType, serviceType),
                data: trends.map(t => getDataValue(t, analysisType)),
                borderColor: CONFIG.CHART_COLORS[serviceType.toLowerCase()],
                backgroundColor: CONFIG.CHART_COLORS[serviceType.toLowerCase()] + '20',
                tension: 0.4,
                fill: true
            }]
        };
        yAxisLabel = getYAxisLabel(analysisType);
    } else {
        // All services chart
        const services = ['Electricity', 'Gas', 'Water'];
        chartData = {
            labels: data.service_trends.Electricity[analysisType]?.map(t => t.month) || [],
            datasets: services.map(service => {
                const trends = data.service_trends[service][analysisType] || [];
                return {
                    label: service,
                    data: trends.map(t => getDataValue(t, analysisType)),
                    borderColor: CONFIG.CHART_COLORS[service.toLowerCase()],
                    backgroundColor: CONFIG.CHART_COLORS[service.toLowerCase()] + '20',
                    tension: 0.4,
                    fill: false
                };
            })
        };
        yAxisLabel = getYAxisLabel(analysisType);
    }
    
    const chartType = document.querySelector('input[name="chartType"]:checked').id === 'lineChart' ? 'line' : 'bar';
    
    charts.mainAnalyticsChart = new Chart(ctx, {
        type: chartType,
        data: chartData,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top'
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Month'
                    }
                },
                y: {
                    display: true,
                    beginAtZero: false,
                    title: {
                        display: true,
                        text: yAxisLabel
                    },
                    ticks: {
                        // Calculate better scaling based on data range
                        callback: function(value, index, values) {
                            if (analysisType === 'usage') {
                                return value.toFixed(0);
                            } else if (analysisType === 'rates') {
                                return '$' + value.toFixed(4);
                            } else {
                                return '$' + value.toFixed(2);
                            }
                        }
                    }
                }
            }
        }
    });
}

/**
 * Create individual service trend charts
 */
function createServiceTrendCharts(serviceTrends, analysisType) {
    const services = ['Electricity', 'Gas', 'Water'];
    
    services.forEach(service => {
        const chartId = `${service.toLowerCase()}TrendChart`;
        const ctx = document.getElementById(chartId);
        if (!ctx) return;
        
        // Destroy existing chart
        if (charts[chartId]) {
            charts[chartId].destroy();
        }
        
        const trends = serviceTrends[service][analysisType] || [];
        if (trends.length === 0) return;
        
        charts[chartId] = new Chart(ctx, {
            type: 'line',
            data: {
                labels: trends.map(t => t.month),
                datasets: [{
                    label: getDatasetLabel(analysisType, service),
                    data: trends.map(t => getDataValue(t, analysisType)),
                    borderColor: CONFIG.CHART_COLORS[service.toLowerCase()],
                    backgroundColor: CONFIG.CHART_COLORS[service.toLowerCase()] + '20',
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
                    x: {
                        display: false
                    },
                    y: {
                        display: true,
                        beginAtZero: false,
                        title: {
                            display: true,
                            text: getYAxisLabel(analysisType, true)
                        },
                        ticks: {
                            maxTicksLimit: 5,
                            callback: function(value, index, values) {
                                if (analysisType === 'usage') {
                                    return value.toFixed(0);
                                } else if (analysisType === 'rates') {
                                    return '$' + value.toFixed(4);
                                } else {
                                    return '$' + value.toFixed(0);
                                }
                            }
                        }
                    }
                }
            }
        });
    });
}

/**
 * Create rate comparison chart
 */
function createRateComparisonChart(rateData) {
    const ctx = document.getElementById('rateComparisonChart');
    if (!ctx || !rateData) return;
    
    // Destroy existing chart
    if (charts.rateComparisonChart) {
        charts.rateComparisonChart.destroy();
    }
    
    charts.rateComparisonChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: rateData.map(r => r.service_type),
            datasets: [{
                label: 'Average Rate',
                data: rateData.map(r => r.avg_rate),
                backgroundColor: rateData.map(r => CONFIG.CHART_COLORS[r.service_type.toLowerCase()])
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
                    title: {
                        display: true,
                        text: 'Rate ($/unit)'
                    }
                }
            }
        }
    });
}

/**
 * Create service fee chart
 */
function createServiceFeeChart(serviceTrends) {
    const ctx = document.getElementById('serviceFeeChart');
    if (!ctx) return;
    
    // Destroy existing chart
    if (charts.serviceFeeChart) {
        charts.serviceFeeChart.destroy();
    }
    
    const services = ['Electricity', 'Gas', 'Water'];
    const datasets = services.map(service => {
        const trends = serviceTrends[service].service_fees || [];
        return {
            label: service,
            data: trends.map(t => t.avg_service_charge),
            borderColor: CONFIG.CHART_COLORS[service.toLowerCase()],
            backgroundColor: CONFIG.CHART_COLORS[service.toLowerCase()] + '20',
            tension: 0.4
        };
    });
    
    // Use the longest label array
    const labels = serviceTrends.Electricity?.service_fees?.map(t => t.month) || [];
    
    charts.serviceFeeChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top'
                }
            },
            scales: {
                y: {
                    title: {
                        display: true,
                        text: 'Service Fees ($)'
                    }
                }
            }
        }
    });
}

/**
 * Update service statistics table
 */
function updateServiceStats(serviceStats) {
    const container = document.getElementById('serviceStats');
    if (!container || !serviceStats) return;
    
    let tableHtml = `
        <table class="table table-hover">
            <thead>
                <tr>
                    <th>Service</th>
                    <th>Invoices</th>
                    <th>Total Amount</th>
                    <th>Avg Amount</th>
                    <th>Avg Rate</th>
                    <th>Total Usage</th>
                </tr>
            </thead>
            <tbody>`;
    
    Object.entries(serviceStats).forEach(([service, stats]) => {
        const serviceIcon = {
            'Electricity': '⚡',
            'Gas': '🔥',
            'Water': '💧'
        }[service] || '';
        
        tableHtml += `
            <tr>
                <td><strong>${serviceIcon} ${service}</strong></td>
                <td>${stats.total_invoices}</td>
                <td>$${stats.total_amount.toFixed(2)}</td>
                <td>$${stats.avg_amount.toFixed(2)}</td>
                <td>$${stats.avg_rate.toFixed(4)}</td>
                <td>${stats.total_usage.toFixed(2)}</td>
            </tr>`;
    });
    
    tableHtml += '</tbody></table>';
    container.innerHTML = tableHtml;
}

/**
 * Update cost breakdown analysis
 */
function updateCostBreakdown(costBreakdown) {
    const container = document.getElementById('costBreakdown');
    if (!container || !costBreakdown) return;
    
    let breakdownHtml = '';
    costBreakdown.forEach(breakdown => {
        const serviceIcon = {
            'Electricity': '⚡',
            'Gas': '🔥', 
            'Water': '💧'
        }[breakdown.service_type] || '';
        
        breakdownHtml += `
            <div class="mb-3">
                <h6>${serviceIcon} ${breakdown.service_type}</h6>
                <div class="row">
                    <div class="col-sm-6">
                        <small class="text-muted">Service Charges</small>
                        <div class="fw-bold text-warning">
                            $${breakdown.total_service_charges.toFixed(2)} 
                            (${breakdown.service_charge_percentage.toFixed(1)}%)
                        </div>
                    </div>
                    <div class="col-sm-6">
                        <small class="text-muted">Usage Charges</small>
                        <div class="fw-bold text-primary">
                            $${breakdown.total_usage_charges.toFixed(2)} 
                            (${breakdown.usage_charge_percentage.toFixed(1)}%)
                        </div>
                    </div>
                </div>
                <div class="progress mt-2" style="height: 8px;">
                    <div class="progress-bar bg-warning" style="width: ${breakdown.service_charge_percentage}%"></div>
                    <div class="progress-bar bg-primary" style="width: ${breakdown.usage_charge_percentage}%"></div>
                </div>
            </div>`;
    });
    
    container.innerHTML = breakdownHtml;
}

// Helper functions for chart data processing
function getDatasetLabel(analysisType, service) {
    const labels = {
        'spending': `${service} Spending`,
        'usage': `${service} Usage`,
        'rates': `${service} Rate`, 
        'service_fees': `${service} Service Fees`
    };
    return labels[analysisType] || 'Data';
}

function getDataValue(dataPoint, analysisType) {
    switch (analysisType) {
        case 'spending': return dataPoint.total_amount || dataPoint.avg_amount || 0;
        case 'usage': return dataPoint.total_usage || dataPoint.avg_usage || 0;
        case 'rates': return dataPoint.avg_rate || 0;
        case 'service_fees': return dataPoint.avg_service_charge || dataPoint.total_service_charge || 0;
        default: return 0;
    }
}

function getYAxisLabel(analysisType, short = false) {
    const labels = {
        'spending': short ? '$' : 'Amount ($)',
        'usage': short ? 'Units' : 'Usage (kWh/m³/kL)',
        'rates': short ? '$/unit' : 'Rate ($/unit)',
        'service_fees': short ? '$' : 'Service Fees ($)'
    };
    return labels[analysisType] || 'Value';
}

// Set up event listeners for chart type changes
$(document).ready(function() {
    $('input[name="chartType"]').change(function() {
        // Reload main chart with new type
        if (window.currentAnalyticsData) {
            const serviceType = document.getElementById('analyticsServiceFilter').value;
            const analysisType = document.getElementById('analyticsTypeFilter').value;
            createMainAnalyticsChart(window.currentAnalyticsData, analysisType, serviceType);
        }
    });
});

// Set up event listeners for utility attributes form changes
$(document).ready(function() {
    // Billing cycle change events
    $('#elecBillingCycle').change(function() {
        toggleCustomFields('elec', $(this).val(), $('#elecDueDate').val());
    });
    $('#gasBillingCycle').change(function() {
        toggleCustomFields('gas', $(this).val(), $('#gasDueDate').val());
    });
    $('#waterBillingCycle').change(function() {
        toggleCustomFields('water', $(this).val(), $('#waterDueDate').val());
    });
    
    // Due date change events
    $('#elecDueDate').change(function() {
        toggleCustomFields('elec', $('#elecBillingCycle').val(), $(this).val());
    });
    $('#gasDueDate').change(function() {
        toggleCustomFields('gas', $('#gasBillingCycle').val(), $(this).val());
    });
    $('#waterDueDate').change(function() {
        toggleCustomFields('water', $('#waterBillingCycle').val(), $(this).val());
    });
});