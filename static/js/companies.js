document.addEventListener('DOMContentLoaded', function() {
    const companiesTable = document.getElementById('companiesTable');
    const addCompanyForm = document.getElementById('addCompanyForm');
    const saveCompanyBtn = document.getElementById('saveCompany');
    const searchInput = document.querySelector('.search-input input');
    const addCompanyModal = new bootstrap.Modal(document.getElementById('addCompanyModal'));
    let editMode = false;
    let editCompanyId = null;

    // Add event delegation for edit/delete buttons
    companiesTable.addEventListener('click', function(e) {
        const target = e.target.closest('button');
        if (!target) return;
        
        const row = target.closest('tr');
        const companyId = row.dataset.id;
        
        if (target.classList.contains('edit-company')) {
            editCompany(companyId);
        } else if (target.classList.contains('delete-company')) {
            if (confirm('Biztosan törli ezt a céget?')) {
                deleteCompany(companyId);
            }
        }
    });

    // Add email field handling
    document.getElementById('addEmailField').addEventListener('click', () => {
        const emailInputs = document.getElementById('emailInputs');
        const newGroup = document.createElement('div');
        newGroup.className = 'email-input-group mb-2 d-flex';
        newGroup.innerHTML = `
            <input type="email" class="form-control" name="companyEmails[]" required>
            <button type="button" class="btn btn-light ms-2 remove-email">
                <i class="bi bi-trash"></i>
            </button>
        `;
        emailInputs.appendChild(newGroup);
    });

    document.getElementById('emailInputs').addEventListener('click', (e) => {
        if (e.target.closest('.remove-email')) {
            const group = e.target.closest('.email-input-group');
            if (document.querySelectorAll('.email-input-group').length > 1) {
                group.remove();
            }
        }
    });

    async function editCompany(id) {
        try {
            const response = await fetch(`/api/companies/${id}`, {
                headers: {
                    'Accept': 'application/json'
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const result = await response.json();
            
            if (result.success) {
                editMode = true;
                editCompanyId = id;
                
                // Update modal title
                const modalTitle = document.querySelector('#addCompanyModal .modal-title');
                modalTitle.textContent = 'Cég szerkesztése';
                
                // Fill form with company data
                document.getElementById('companyName').value = result.data.name;
                
                // Clear existing email inputs except the first one
                const emailInputs = document.getElementById('emailInputs');
                emailInputs.innerHTML = '';
                
                // Add email inputs for each email
                result.data.emails.forEach((email, index) => {
                    const emailGroup = document.createElement('div');
                    emailGroup.className = 'email-input-group mb-2 d-flex';
                    emailGroup.innerHTML = `
                        <input type="email" class="form-control" name="companyEmails[]" value="${email}" required>
                        <button type="button" class="btn btn-light ms-2 remove-email" ${index === 0 ? 'style="display: none;"' : ''}>
                            <i class="bi bi-trash"></i>
                        </button>
                    `;
                    emailInputs.appendChild(emailGroup);
                });
                
                // Show modal
                addCompanyModal.show();
            }
        } catch (error) {
            console.error('Error loading company data:', error);
            showError('Nem sikerült betölteni a cég adatait');
        }
    }

    function deleteCompany(id) {
        fetch(`/api/companies/${id}`, {
            method: 'DELETE',
            headers: {
                'Accept': 'application/json'
            }
        })
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                loadCompanies();
            } else {
                showError(result.message || 'Nem sikerült törölni a céget');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showError('Nem sikerült törölni a céget');
        });
    }

    // Load companies with improved error handling
    async function loadCompanies() {
        try {
            const response = await fetch('/api/companies', {
                headers: {
                    'Accept': 'application/json'
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                throw new TypeError("Response was not JSON");
            }
            
            const result = await response.json();
            
            if (result.success && Array.isArray(result.data)) {
                companiesTable.innerHTML = '';
                result.data.forEach(company => {
                    const row = document.createElement('tr');
                    row.dataset.id = company.id;
                    row.innerHTML = `
                        <td>${company.name || ''}</td>
                        <td>${(company.emails || []).join(', ')}</td>
                        <td>${company.email_count || 0}</td>
                        <td>
                            <button class="btn btn-sm btn-light edit-company" data-id="${company.id}">
                                <i class="bi bi-pencil"></i>
                            </button>
                            <button class="btn btn-sm btn-light delete-company" data-id="${company.id}">
                                <i class="bi bi-trash"></i>
                            </button>
                        </td>
                    `;
                    companiesTable.appendChild(row);
                });
            } else {
                throw new Error('Invalid response format');
            }
        } catch (error) {
            console.error('Error loading companies:', error);
            showError('Nem sikerült betölteni a cégeket. Kérem, próbálja újra később.');
        }
    }

    // Show error message function
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

    // Save company with improved error handling
    saveCompanyBtn.addEventListener('click', async () => {
        try {
            const nameInput = document.getElementById('companyName');
            const emailInputs = document.querySelectorAll('[name="companyEmails[]"]');
            
            if (!nameInput.value.trim()) {
                showError('A cégnév megadása kötelező');
                return;
            }
            
            const companyData = {
                name: nameInput.value.trim(),
                emails: Array.from(emailInputs)
                    .map(input => input.value.trim())
                    .filter(email => email)
            };
            
            const url = editMode ? `/api/companies/${editCompanyId}` : '/api/companies';
            const method = editMode ? 'PUT' : 'POST';
            
            const response = await fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify(companyData)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const result = await response.json();
            
            if (result.success) {
                addCompanyModal.hide();
                resetForm();
                loadCompanies();
            } else {
                throw new Error(result.error || 'Failed to save company');
            }
        } catch (error) {
            console.error('Error saving company:', error);
            showError('Nem sikerült menteni a céget. Kérem, próbálja újra később.');
        }
    });

    // Reset form function
    function resetForm() {
        editMode = false;
        editCompanyId = null;
        const nameInput = document.getElementById('companyName');
        nameInput.value = '';
        document.getElementById('emailInputs').innerHTML = `
            <div class="email-input-group mb-2">
                <input type="email" class="form-control" name="companyEmails[]" required>
            </div>
        `;
        // Reset modal title
        const modalTitle = document.querySelector('#addCompanyModal .modal-title');
        modalTitle.textContent = 'Új cég hozzáadása';
    }

    // Reset form when modal is hidden
    document.getElementById('addCompanyModal').addEventListener('hidden.bs.modal', resetForm);

    // Search functionality
    if (searchInput) {
        searchInput.addEventListener('input', () => {
            const searchTerm = searchInput.value.toLowerCase();
            const rows = companiesTable.querySelectorAll('tr');
            
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(searchTerm) ? '' : 'none';
            });
        });
    }

    // Load companies on page load
    loadCompanies();
});
