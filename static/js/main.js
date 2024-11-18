document.addEventListener('DOMContentLoaded', function() {
    // Theme handling
    const themeToggle = document.getElementById('themeToggle');
    const themeIcon = themeToggle?.querySelector('i');
    
    if (themeToggle && themeIcon) {
        themeToggle.addEventListener('click', () => {
            const html = document.documentElement;
            const currentTheme = html.getAttribute('data-bs-theme');
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';
            
            html.setAttribute('data-bs-theme', newTheme);
            themeIcon.classList.toggle('bi-sun-fill');
            themeIcon.classList.toggle('bi-moon-fill');
        });
    }

    // Sidebar toggle
    const sidebarCollapse = document.getElementById('sidebarCollapse');
    const sidebar = document.getElementById('sidebar');
    
    if (sidebarCollapse && sidebar) {
        sidebarCollapse.addEventListener('click', () => {
            sidebar.classList.toggle('active');
        });
    }

    // Constants for retry mechanism
    const MAX_RETRIES = 3;
    const RETRY_DELAY = 2000; // 2 seconds base delay
    let retryCount = 0;

    // Progress indicator
    function showProgress(message) {
        const progressContainer = document.createElement('div');
        progressContainer.className = 'alert alert-info alert-dismissible fade show';
        progressContainer.style.position = 'fixed';
        progressContainer.style.top = '20px';
        progressContainer.style.right = '20px';
        progressContainer.style.zIndex = '9999';
        progressContainer.innerHTML = `
            ${message}
            <div class="progress mt-2">
                <div class="progress-bar progress-bar-striped progress-bar-animated" 
                     role="progressbar" 
                     style="width: 100%"></div>
            </div>
        `;
        document.body.appendChild(progressContainer);
        return progressContainer;
    }

    // Error message handling
    function showError(message) {
        const errorContainer = document.createElement('div');
        errorContainer.className = 'alert alert-danger alert-dismissible fade show';
        errorContainer.style.position = 'fixed';
        errorContainer.style.top = '20px';
        errorContainer.style.right = '20px';
        errorContainer.style.zIndex = '9999';
        errorContainer.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        document.body.appendChild(errorContainer);
        
        setTimeout(() => {
            errorContainer.remove();
        }, 5000);
    }

    async function fetchWithRetry(url, options = {}, retries = MAX_RETRIES) {
        const defaultOptions = {
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            },
            credentials: 'same-origin'
        };
        options = { ...defaultOptions, ...options };
        
        try {
            const response = await fetch(url, options);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        } catch (error) {
            if (retries > 0) {
                await new Promise(resolve => setTimeout(resolve, RETRY_DELAY));
                return fetchWithRetry(url, options, retries - 1);
            }
            throw error;
        }
    }

    // Email monitoring functionality
    const connectionStatus = document.getElementById('connectionStatus');
    const pdfCount = document.getElementById('pdfCount');
    const emailCount = document.getElementById('emailCount');
    const lastCheck = document.getElementById('lastCheck');
    const emailTable = document.getElementById('emailTable');

    // Search functionality
    const searchInput = document.querySelector('.search-input input');
    const statusFilter = document.querySelector('select');

    // Pagination state
    let currentPage = 1;
    let countdown = 10;

    function filterTable() {
        if (!emailTable) return;
        
        const searchTerm = (searchInput?.value || '').toLowerCase();
        const statusTerm = statusFilter?.value || 'Minden státusz';
        const rows = emailTable.querySelectorAll('tr');

        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            const matchesSearch = text.includes(searchTerm);
            row.style.display = matchesSearch ? '' : 'none';
        });
    }

    if (searchInput) {
        searchInput.addEventListener('input', filterTable);
    }
    
    if (statusFilter) {
        statusFilter.addEventListener('change', filterTable);
    }

    async function updateStats() {
        const progressIndicator = showProgress('Statisztikák frissítése...');
        try {
            const result = await fetchWithRetry('/api/stats');
            if (result.success) {
                if (connectionStatus) {
                    connectionStatus.textContent = `${result.stats.companies} cég`;
                }
                if (pdfCount) {
                    pdfCount.textContent = `${result.stats.pdfs} PDF`;
                }
                if (emailCount) {
                    emailCount.textContent = `${result.stats.emails} e-mail`;
                }
            } else {
                showError(result.message || 'Hiba történt a statisztikák frissítésekor');
            }
        } catch (error) {
            console.error('Error updating stats:', error.message);
            showError('Nem sikerült frissíteni a statisztikákat. Újrapróbálkozás folyamatban...');
        } finally {
            progressIndicator.remove();
        }
    }

    function getSenderDisplay(data) {
        if (data.company) {
            return `<div style="font-weight: 500;">${data.company.name}</div>
                    <div style="color: var(--text-secondary); font-size: 13px;">${data.from}</div>`;
        }
        return `<div style="font-weight: 500;">${data.from}</div>`;
    }

    function addEmailToTable(data) {
        if (!emailTable) return;
        
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${data.id}</td>
            <td>${getSenderDisplay(data)}</td>
            <td>
                <span class="status-badge ${data.has_pdf ? 'active' : 'pending'}">
                    ${data.has_pdf ? 'Van' : 'Nincs'}
                </span>
            </td>
            <td>${data.pdf_emails ? data.pdf_emails.join(', ') : '-'}</td>
            <td>${formatDate(data.date)}</td>
            <td>
                <button class="btn btn-sm btn-light delete-email" onclick="deleteEmail(${data.id})">
                    <i class="bi bi-trash"></i>
                </button>
            </td>
        `;
        emailTable.appendChild(row);
    }

    function formatDate(dateStr) {
        if (!dateStr) return '-';
        
        try {
            const date = new Date(dateStr);
            if (isNaN(date.getTime())) {
                throw new Error('Invalid date');
            }
            
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            const hours = String(date.getHours()).padStart(2, '0');
            const minutes = String(date.getMinutes()).padStart(2, '0');
            
            return `${year}. ${month}. ${day}. ${hours}:${minutes}`;
        } catch (error) {
            console.error('Error formatting date:', error);
            return dateStr;
        }
    }

    window.deleteEmail = async function(emailId) {
        if (confirm('Biztosan törli ezt az e-mailt?')) {
            const progressIndicator = showProgress('E-mail törlése...');
            try {
                const result = await fetchWithRetry(`/api/emails/${emailId}`, {
                    method: 'DELETE'
                });
                
                if (result.success) {
                    loadExistingEmails(currentPage);
                    updateStats();
                } else {
                    showError(result.message || 'Hiba történt az e-mail törlése közben');
                }
            } catch (error) {
                console.error('Error deleting email:', error.message);
                showError('Nem sikerült törölni az e-mailt. Kérjük, próbálja újra később.');
            } finally {
                progressIndicator.remove();
            }
        }
    }

    async function loadExistingEmails(page = 1) {
        try {
            const timestamp = new Date().getTime();
            const response = await fetch(`/api/emails?page=${page}&t=${timestamp}`, {
                headers: {
                    'Accept': 'application/json',
                    'Cache-Control': 'no-cache'
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const result = await response.json();
            
            if (result.success) {
                if (emailTable) {
                    emailTable.innerHTML = '';
                    if (Array.isArray(result.data)) {
                        result.data.forEach(email => {
                            addEmailToTable(email);
                        });
                    }
                    
                    // Update pagination
                    currentPage = result.pagination.page;
                    updatePaginationControls(result.pagination);
                }
            }
        } catch (error) {
            console.error('Error loading emails:', error);
            showError('Nem sikerült betölteni az e-maileket');
        }
    }

    async function checkLatestEmail() {
        const progressIndicator = showProgress('Új e-mailek ellenőrzése...');
        try {
            const result = await fetchWithRetry('/check-latest');
            if (result.success) {
                // Add timestamp to prevent caching
                const timestamp = new Date().getTime();
                const response = await fetchWithRetry(`/api/emails?page=1&t=${timestamp}`);
                
                if (response.success && emailTable) {
                    emailTable.innerHTML = '';
                    if (Array.isArray(response.data)) {
                        response.data.forEach(email => {
                            addEmailToTable(email);
                        });
                    }
                    
                    // Update pagination
                    currentPage = response.pagination.page;
                    updatePaginationControls(response.pagination);
                }
                
                await updateStats();
            }
        } catch (error) {
            console.error('Error checking latest email:', error.message);
            showError('Nem sikerült ellenőrizni az új e-maileket. Újrapróbálkozás folyamatban...');
        } finally {
            progressIndicator.remove();
        }
    }

    function updatePaginationControls(pagination) {
        const pageInfo = document.getElementById('pageInfo');
        const prevPageBtn = document.getElementById('prevPage');
        const nextPageBtn = document.getElementById('nextPage');
        
        if (pageInfo) {
            const start = (pagination.page - 1) * 10 + 1;
            const end = Math.min(pagination.page * 10, pagination.total);
            pageInfo.textContent = `${start}-${end} / ${pagination.total} találat`;
        }
        
        if (prevPageBtn) prevPageBtn.disabled = pagination.page <= 1;
        if (nextPageBtn) nextPageBtn.disabled = pagination.page >= pagination.pages;
    }

    // Add pagination event listeners
    document.getElementById('prevPage')?.addEventListener('click', () => {
        if (currentPage > 1) {
            loadExistingEmails(currentPage - 1);
        }
    });

    document.getElementById('nextPage')?.addEventListener('click', () => {
        loadExistingEmails(currentPage + 1);
    });

    async function updateCountdown() {
        if (lastCheck) {
            lastCheck.textContent = `${countdown} mp`;
            countdown--;
            
            if (countdown < 0) {
                countdown = 10;
                await checkLatestEmail();
            }
        }
    }

    // Start auto-refresh when page loads
    function startAutoRefresh() {
        if (emailTable) {
            // Initial load
            loadExistingEmails(1)
                .then(() => updateStats())
                .then(() => {
                    // Set up intervals with error handling
                    setInterval(() => {
                        updateCountdown().catch(console.error);
                    }, 1000);
                    
                    setInterval(() => {
                        updateStats().catch(console.error);
                    }, 10000);
                })
                .catch(error => {
                    console.error('Error during initialization:', error);
                    showError('Nem sikerült betölteni az adatokat. Újrapróbálkozás folyamatban...');
                });
        }
    }

    startAutoRefresh();
});
