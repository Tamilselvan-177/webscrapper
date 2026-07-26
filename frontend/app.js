document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('search-form');
    const jobGrid = document.getElementById('job-grid');
    const statusPanel = document.getElementById('status-panel');
    const errorAlert = document.getElementById('error-alert');
    const errorMsg = document.getElementById('error-msg');
    const metricsPanel = document.getElementById('metrics-panel');
    const countValue = document.getElementById('count-value');
    const loader = document.getElementById('loader');
    
    const sourceSelect = document.getElementById('source');
    const companyInput = document.getElementById('company');
    const companyLabel = document.querySelector('label[for="company"]');

    const atsSystems = ['greenhouse', 'lever', 'smartrecruiters', 'personio', 'ashby'];

    sourceSelect.addEventListener('change', (e) => {
        if (atsSystems.includes(e.target.value)) {
            companyInput.required = true;
            companyLabel.textContent = 'Company Slug (Required for ATS)';
            companyInput.placeholder = 'e.g. openai, netflix, contentful';
        } else {
            companyInput.required = false;
            companyLabel.textContent = 'Company Slug / Name (Optional)';
            companyInput.placeholder = 'e.g. amazon (Leave blank for general search)';
        }
    });

    // Trigger once on load to set initial state
    sourceSelect.dispatchEvent(new Event('change'));

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Reset UI
        jobGrid.innerHTML = '';
        statusPanel.classList.remove('hidden');
        errorAlert.classList.add('hidden');
        metricsPanel.classList.add('hidden');
        loader.classList.remove('hidden');
        
        // Build URL
        const source = document.getElementById('source').value;
        const company = document.getElementById('company').value.trim();
        const keyword = document.getElementById('keyword').value.trim();
        const locationInput = document.getElementById('location').value.trim();
        
        const host = window.location.hostname || 'localhost';
        // Dynamically connect to port 8080 (Docker) or 8000 (Local Uvicorn)
        const port = window.location.port === '3000' || window.location.port === '' ? '8080' : '8000';
        let url = `http://${host}:${port}/api/v1/jobs?source=${encodeURIComponent(source)}`;
        
        if (company) {
            url += `&company=${encodeURIComponent(company)}`;
        }
        if (keyword) {
            url += `&keyword=${encodeURIComponent(keyword)}`;
        }
        if (locationInput) {
            url += `&city=${encodeURIComponent(locationInput)}`;
        }

        try {
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`API Error: ${response.status} ${response.statusText}`);
            }
            
            const jobs = await response.json();
            
            // Hide loader
            loader.classList.add('hidden');
            
            // Update metrics
            countValue.textContent = jobs.length;
            metricsPanel.classList.remove('hidden');
            
            if (jobs.length === 0) {
                errorAlert.classList.remove('hidden');
                errorAlert.style.borderLeftColor = 'var(--accent-secondary)';
                errorAlert.style.color = 'var(--accent-secondary)';
                errorMsg.textContent = 'No jobs found for this search criteria.';
                return;
            }
            
            // Render Jobs
            jobs.forEach(job => {
                const card = document.createElement('div');
                card.className = 'job-card';
                
                const location = [job.city, job.state, job.country].filter(Boolean).join(', ') || 'Location N/A';
                const remoteBadge = job.remote ? `<span class="meta-item remote">Remote</span>` : '';
                const typeBadge = job.employment_type ? `<span class="meta-item">${job.employment_type}</span>` : '';
                
                const logoHtml = job.company_logo ? `<img src="${job.company_logo}" alt="${job.company} logo" style="width: 40px; height: 40px; border-radius: 4px; object-fit: contain; margin-right: 12px; flex-shrink: 0;">` : '';
                
                const datesHtml = [];
                const openDate = job.open_time || job.posted_date;
                if (openDate) datesHtml.push(`Opened: ${openDate}`);
                if (job.close_time) datesHtml.push(`Closes: ${job.close_time}`);
                const dateBadge = datesHtml.length > 0 ? `<div class="meta-item" style="font-size: 0.8em; margin-top: 8px; opacity: 0.8;">📅 ${datesHtml.join(' | ')}</div>` : '';
                
                const applicantsBadge = (job.applicants !== null && job.applicants !== undefined) ? `<div class="meta-item" style="font-size: 0.8em; margin-top: 4px; color: var(--accent-primary);">👥 ${job.applicants} applicants</div>` : '';
                
                const descHtml = job.description && job.description !== "Click the 'View Job' button to read the full description on LinkedIn."
                    ? `<div class="job-description" style="font-size: 0.85em; margin-top: 8px; opacity: 0.9; max-height: 60px; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;">${job.description}</div>`
                    : '';
                
                card.innerHTML = `
                    <div style="display: flex; align-items: center; margin-bottom: 12px;">
                        ${logoHtml}
                        <h3 style="margin: 0; line-height: 1.2;">${job.title}</h3>
                    </div>
                    <div class="company-location">
                        ${job.company} • ${location}
                    </div>
                    <div class="meta-grid" style="margin-bottom: 4px;">
                        ${remoteBadge}
                        ${typeBadge}
                    </div>
                    ${dateBadge}
                    ${applicantsBadge}
                    ${descHtml}
                    <a href="${job.apply_url || job.job_url}" target="_blank" class="apply-btn" style="margin-top: 12px;">View Job</a>
                `;
                
                jobGrid.appendChild(card);
            });
            
        } catch (error) {
            loader.classList.add('hidden');
            errorAlert.classList.remove('hidden');
            errorAlert.style.borderLeftColor = 'var(--accent-alert)';
            errorAlert.style.color = 'var(--accent-alert)';
            errorMsg.textContent = error.message;
        }
    });
});
