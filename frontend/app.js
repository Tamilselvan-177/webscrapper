document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('search-form');
    const jobGrid = document.getElementById('job-grid');
    const statusPanel = document.getElementById('status-panel');
    const errorAlert = document.getElementById('error-alert');
    const errorMsg = document.getElementById('error-msg');
    const metricsPanel = document.getElementById('metrics-panel');
    const countValue = document.getElementById('count-value');
    const loader = document.getElementById('loader');

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
        const company = document.getElementById('company').value;
        const keyword = document.getElementById('keyword').value;
        
        let url = `http://localhost:8000/api/v1/jobs?source=${encodeURIComponent(source)}&company=${encodeURIComponent(company)}`;
        if (keyword) {
            url += `&keyword=${encodeURIComponent(keyword)}`;
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
                
                card.innerHTML = `
                    <h3>${job.title}</h3>
                    <div class="company-location">
                        ${job.company} • ${location}
                    </div>
                    <div class="meta-grid">
                        ${remoteBadge}
                        ${typeBadge}
                    </div>
                    <a href="${job.apply_url || job.job_url}" target="_blank" class="apply-btn">View Job</a>
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
