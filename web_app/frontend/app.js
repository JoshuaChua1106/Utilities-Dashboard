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