/**
 * AI Job Search Agent - Client Application Logic.
 * Dual-Mode Data Layer (FastAPI API or Static Vercel / PWA Offline Cache),
 * Live Search & Multi-Faceted Filtering, Application Status Tracker, and CSV Export.
 */

// State
let allJobs = [];
let filteredJobs = [];
let currentJobInModal = null;
let currentMode = 'static'; // 'api' | 'static' | 'offline'

let state = {
  searchQuery: '',
  selectedPortal: 'all',
  minScore: 70,
  workplaceType: 'all',
  activeTab: 'all',
  viewMode: 'grid' // 'grid' | 'table'
};

// Portal Metadata Map
const PORTAL_META = {
  topjobs_lk: { label: 'TopJobs.lk', class: 'badge-portal-topjobs_lk' },
  itpro_lk: { label: 'ITPro.lk', class: 'badge-portal-itpro_lk' },
  rooster_jobs: { label: 'Rooster.jobs', class: 'badge-portal-rooster_jobs' },
  xpress_jobs: { label: 'Xpress.jobs', class: 'badge-portal-xpress_jobs' },
  linkedin_guest: { label: 'LinkedIn', class: 'badge-portal-linkedin_guest' }
};

// Local Storage Keys for Static / Offline Persistence
const STORAGE_BOOKMARKS_KEY = 'job_agent_bookmarks';
const STORAGE_APPLIED_KEY = 'job_agent_applied';
const STORAGE_OMITTED_KEY = 'job_agent_omitted';
const STORAGE_NOTES_KEY = 'job_agent_notes';

function getLocalBookmarks() {
  try { return JSON.parse(localStorage.getItem(STORAGE_BOOKMARKS_KEY)) || {}; }
  catch { return {}; }
}
function setLocalBookmarks(data) { localStorage.setItem(STORAGE_BOOKMARKS_KEY, JSON.stringify(data)); }

function getLocalApplied() {
  try { return JSON.parse(localStorage.getItem(STORAGE_APPLIED_KEY)) || {}; }
  catch { return {}; }
}
function setLocalApplied(data) { localStorage.setItem(STORAGE_APPLIED_KEY, JSON.stringify(data)); }

function getLocalOmitted() {
  try { return JSON.parse(localStorage.getItem(STORAGE_OMITTED_KEY)) || {}; }
  catch { return {}; }
}
function setLocalOmitted(data) { localStorage.setItem(STORAGE_OMITTED_KEY, JSON.stringify(data)); }

function getLocalNotes() {
  try { return JSON.parse(localStorage.getItem(STORAGE_NOTES_KEY)) || {}; }
  catch { return {}; }
}
function setLocalNotes(data) { localStorage.setItem(STORAGE_NOTES_KEY, JSON.stringify(data)); }

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  initServiceWorker();
  initNetworkListeners();
  initEventListeners();
  loadData();
});

// PWA Service Worker Registration
function initServiceWorker() {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch((err) => {
      console.debug('Service Worker registration skipped or failed:', err);
    });
  }
}

// Online / Offline Status Listeners
function initNetworkListeners() {
  const toast = document.getElementById('offlineToast');
  function updateOnlineStatus() {
    if (!navigator.onLine) {
      toast.classList.remove('hidden');
      toast.classList.add('flex');
    } else {
      toast.classList.add('hidden');
      toast.classList.remove('flex');
    }
  }
  window.addEventListener('online', updateOnlineStatus);
  window.addEventListener('offline', updateOnlineStatus);
  updateOnlineStatus();
}

// Dual-Mode Data Loader
async function loadData() {
  const badge = document.getElementById('connectionBadge');
  const btnSweep = document.getElementById('btnTriggerSweep');

  try {
    // 1. Try FastAPI REST API first (Local Server Mode)
    const apiRes = await fetch('/api/jobs?limit=500');
    if (apiRes.ok) {
      const data = await apiRes.json();
      allJobs = data.jobs || [];
      currentMode = 'api';
      badge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> Local Server`;
      badge.className = "text-[10px] px-2 py-0.5 rounded-full font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1";
      btnSweep.classList.remove('hidden');
      btnSweep.classList.add('flex');
      applyFilters();
      return;
    }
  } catch (e) {
    // Local API not responding, fall back to static data
  }

  try {
    // 2. Fall back to static bundle (/data/jobs.json for Vercel / PWA)
    const staticRes = await fetch('/data/jobs.json');
    if (staticRes.ok) {
      const payload = await staticRes.json();
      allJobs = payload.jobs || [];
      currentMode = 'static';
      badge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-cyan-400"></span> Cloud Vercel`;
      badge.className = "text-[10px] px-2 py-0.5 rounded-full font-medium bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 flex items-center gap-1";
      btnSweep.classList.add('hidden');
      
      // Merge local bookmarks and notes
      mergeLocalStorageTracking();
      applyFilters();
      return;
    }
  } catch (err) {
    console.warn('Failed to load static jobs.json:', err);
  }

  // 3. Fallback to cached jobs in localStorage if totally offline
  const cached = localStorage.getItem('cached_jobs_payload');
  if (cached) {
    allJobs = JSON.parse(cached);
    currentMode = 'offline';
    badge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-amber-400"></span> Offline Cache`;
    mergeLocalStorageTracking();
    applyFilters();
  } else {
    document.getElementById('jobsContainer').innerHTML = `
      <div class="col-span-full py-16 text-center text-slate-400">
        <p class="font-bold text-white text-base mb-1">No Jobs Found</p>
        <p class="text-xs">Run <code class="text-brand-400">python main.py --run-once</code> or export data first.</p>
      </div>
    `;
  }
}

// Merge localStorage into jobs for static/offline mode
function mergeLocalStorageTracking() {
  const bookmarks = getLocalBookmarks();
  const applied = getLocalApplied();
  const omitted = getLocalOmitted();
  const notes = getLocalNotes();

  allJobs.forEach((job) => {
    if (bookmarks[job.id]) job.user_status = 'BOOKMARKED';
    if (applied[job.id]) job.user_status = 'APPLIED';
    if (omitted[job.id]) job.user_status = 'OMITTED';
    if (notes[job.id]) job.user_notes = notes[job.id];
  });
}

// Event Listeners
function initEventListeners() {
  // Search Input
  const searchInput = document.getElementById('searchInput');
  const btnClearSearch = document.getElementById('btnClearSearch');

  searchInput.addEventListener('input', (e) => {
    state.searchQuery = e.target.value.trim().toLowerCase();
    if (state.searchQuery) {
      btnClearSearch.classList.remove('hidden');
    } else {
      btnClearSearch.classList.add('hidden');
    }
    applyFilters();
  });

  btnClearSearch.addEventListener('click', () => {
    searchInput.value = '';
    state.searchQuery = '';
    btnClearSearch.classList.add('hidden');
    applyFilters();
  });

  // Portal Filter Buttons
  document.querySelectorAll('.filter-portal-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-portal-btn').forEach((b) => {
        b.className = "filter-portal-btn px-2.5 py-1 text-xs rounded-lg font-medium bg-[#090d16] text-slate-300 hover:bg-dark-hover border border-dark-border transition";
      });
      btn.className = "filter-portal-btn px-2.5 py-1 text-xs rounded-lg font-medium bg-brand-500 text-white transition";
      state.selectedPortal = btn.dataset.portal;
      applyFilters();
    });
  });

  // Score Filter
  document.getElementById('scoreFilter').addEventListener('change', (e) => {
    state.minScore = parseInt(e.target.value, 10);
    applyFilters();
  });

  // Workplace Filter
  document.getElementById('workplaceFilter').addEventListener('change', (e) => {
    state.workplaceType = e.target.value;
    applyFilters();
  });

  // Tabs (Desktop & Top Bar)
  document.querySelectorAll('.tab-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach((b) => {
        b.className = "tab-btn px-3 py-2 border-b-2 border-transparent text-slate-400 hover:text-white transition";
      });
      btn.className = "tab-btn px-3 py-2 border-b-2 border-brand-500 text-brand-400 font-semibold transition";
      state.activeTab = btn.dataset.tab;
      syncMobileNav(btn.dataset.tab);
      applyFilters();
    });
  });

  // Mobile Bottom Navigation Tabs
  document.querySelectorAll('.mobile-nav-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.nav;
      state.activeTab = tab;
      syncMobileNav(tab);
      syncTopTabs(tab);
      applyFilters();
    });
  });

  // View Mode Toggles
  const btnGrid = document.getElementById('btnViewGrid');
  const btnTable = document.getElementById('btnViewTable');

  btnGrid.addEventListener('click', () => {
    state.viewMode = 'grid';
    btnGrid.className = "p-1 rounded text-white bg-dark-hover";
    btnTable.className = "p-1 rounded text-slate-400 hover:text-white";
    document.getElementById('jobsContainer').classList.remove('hidden');
    document.getElementById('tableViewContainer').classList.add('hidden');
  });

  btnTable.addEventListener('click', () => {
    state.viewMode = 'table';
    btnTable.className = "p-1 rounded text-white bg-dark-hover";
    btnGrid.className = "p-1 rounded text-slate-400 hover:text-white";
    document.getElementById('jobsContainer').classList.add('hidden');
    document.getElementById('tableViewContainer').classList.remove('hidden');
    renderTable();
  });

  // Export CSV
  document.getElementById('btnExportCSV').addEventListener('click', exportToCSV);

  // Refresh
  document.getElementById('btnRefresh').addEventListener('click', loadData);

  // Trigger Sweep (Local Mode)
  document.getElementById('btnTriggerSweep').addEventListener('click', async () => {
    if (confirm('Trigger on-demand multi-portal job sweep now?')) {
      try {
        const res = await fetch('/api/trigger-sweep', { method: 'POST' });
        if (res.ok) {
          alert('Job sweep initiated in the background! Refresh in a couple minutes.');
        }
      } catch (e) {
        alert('Could not trigger sweep: ' + e);
      }
    }
  });

  // Modal Close
  document.getElementById('btnCloseModal').addEventListener('click', closeModal);
  document.getElementById('jobModal').addEventListener('click', (e) => {
    if (e.target.id === 'jobModal') closeModal();
  });

  // Modal Save Tracker Notes
  document.getElementById('modalBtnSaveNotes').addEventListener('click', saveModalTracker);
}

function syncMobileNav(tab) {
  document.querySelectorAll('.mobile-nav-btn').forEach((b) => {
    if (b.dataset.nav === tab) {
      b.className = "mobile-nav-btn flex flex-col items-center gap-1 text-brand-400 font-semibold";
    } else {
      b.className = "mobile-nav-btn flex flex-col items-center gap-1 text-slate-400";
    }
  });
}

function syncTopTabs(tab) {
  document.querySelectorAll('.tab-btn').forEach((b) => {
    if (b.dataset.tab === tab) {
      b.className = "tab-btn px-3 py-2 border-b-2 border-brand-500 text-brand-400 font-semibold transition";
    } else {
      b.className = "tab-btn px-3 py-2 border-b-2 border-transparent text-slate-400 hover:text-white transition";
    }
  });
}

// Filtering Engine
function applyFilters() {
  const bookmarks = getLocalBookmarks();
  const appliedList = getLocalApplied();
  const omitted = getLocalOmitted();

  filteredJobs = allJobs.filter((job) => {
    const evalData = job.evaluation || {};
    const score = evalData.match_score || 0;
    const title = (job.title || '').toLowerCase();
    const company = (job.company || '').toLowerCase();
    const location = (job.location || '').toLowerCase();
    const skills = (evalData.matching_skills || []).map(s => s.toLowerCase()).join(' ');
    
    const isOmitted = Boolean(omitted[job.id]) || job.user_status === 'OMITTED';
    const isApplied = Boolean(appliedList[job.id]) || job.user_status === 'APPLIED';
    const isBookmarked = (Boolean(bookmarks[job.id]) || job.user_status === 'BOOKMARKED') && !isOmitted && !isApplied;

    // 1. Text Search Filter
    if (state.searchQuery) {
      const matchText = `${title} ${company} ${location} ${skills}`;
      if (!matchText.includes(state.searchQuery)) return false;
    }

    // 2. Portal Source Filter
    if (state.selectedPortal !== 'all' && job.source !== state.selectedPortal) {
      return false;
    }

    // 3. Minimum Match Score Filter
    if (state.minScore > 0 && score < state.minScore) {
      return false;
    }

    // 4. Workplace Type Filter
    if (state.workplaceType !== 'all') {
      const wp = (job.workplace_type || '').toLowerCase();
      if (state.workplaceType === 'remote' && !wp.includes('remote')) return false;
      if (state.workplaceType === 'hybrid' && !wp.includes('hybrid')) return false;
      if (state.workplaceType === 'on-site' && !wp.includes('on-site') && !wp.includes('onsite')) return false;
    }

    // 5. Category Tab Filter (Strict Tab Segregation)
    if (state.activeTab === 'omitted') {
      // Omit tab displays ONLY omitted jobs
      if (!isOmitted) return false;
    } else if (state.activeTab === 'applied') {
      // Applied tab displays ONLY applied jobs
      if (!isApplied) return false;
    } else if (state.activeTab === 'bookmarked') {
      // Bookmarked tab displays active bookmarked jobs (excluding omitted & applied)
      if (!isBookmarked || isOmitted || isApplied) return false;
    } else if (state.activeTab === 'high_match') {
      // High match tab displays active jobs >= 70% fit (excluding omitted & applied)
      if (isOmitted || isApplied || score < 70) return false;
    } else if (state.activeTab === 'all') {
      // All Listings tab displays active jobs only (excluding omitted & applied)
      if (isOmitted || isApplied) return false;
    }

    return true;
  });

  updateKPICounters();
  renderCards();
  if (state.viewMode === 'table') renderTable();
}

// Update KPI Stats
function updateKPICounters() {
  const bookmarks = getLocalBookmarks();
  const appliedList = getLocalApplied();
  const omitted = getLocalOmitted();

  const omittedCount = allJobs.filter(j => j.user_status === 'OMITTED' || Boolean(omitted[j.id])).length;
  const appliedCount = allJobs.filter(j => j.user_status === 'APPLIED' || Boolean(appliedList[j.id])).length;
  
  // Active jobs are those not omitted and not applied
  const activeJobs = allJobs.filter(j => {
    const isO = j.user_status === 'OMITTED' || Boolean(omitted[j.id]);
    const isA = j.user_status === 'APPLIED' || Boolean(appliedList[j.id]);
    return !isO && !isA;
  });

  const totalActive = activeJobs.length;
  const high = activeJobs.filter(j => (j.evaluation?.match_score || 0) >= 70).length;
  const bookmarked = activeJobs.filter(j => j.user_status === 'BOOKMARKED' || Boolean(bookmarks[j.id])).length;

  // KPI Grid Cards
  const kpiTotal = document.getElementById('kpiTotalJobs');
  if (kpiTotal) kpiTotal.textContent = totalActive;

  const kpiHigh = document.getElementById('kpiHighMatches');
  if (kpiHigh) kpiHigh.textContent = high;

  const kpiBm = document.getElementById('kpiBookmarked');
  if (kpiBm) kpiBm.textContent = bookmarked;

  const kpiApp = document.getElementById('kpiApplied');
  if (kpiApp) kpiApp.textContent = appliedCount;

  const kpiOmit = document.getElementById('kpiOmitted');
  if (kpiOmit) kpiOmit.textContent = omittedCount;

  // Tab Badge Counters
  const tabAll = document.getElementById('countTabAll');
  if (tabAll) tabAll.textContent = totalActive;

  const tabHigh = document.getElementById('countTabHigh');
  if (tabHigh) tabHigh.textContent = high;

  const tabBm = document.getElementById('countTabBookmarked');
  if (tabBm) tabBm.textContent = bookmarked;

  const tabApp = document.getElementById('countTabApplied');
  if (tabApp) tabApp.textContent = appliedCount;

  const tabOmit = document.getElementById('countTabOmitted');
  if (tabOmit) tabOmit.textContent = omittedCount;

  const vis = document.getElementById('visibleCount');
  if (vis) vis.textContent = filteredJobs.length;
}

// Render Job Cards (Grid View)
function renderCards() {
  const container = document.getElementById('jobsContainer');
  if (!container) return;

  if (filteredJobs.length === 0) {
    container.innerHTML = `
      <div class="col-span-full py-16 text-center text-slate-400">
        <i data-lucide="search-x" class="w-8 h-8 mx-auto mb-2 text-slate-500"></i>
        <p class="font-bold text-white text-sm mb-1">No Matching Jobs</p>
        <p class="text-xs">Try clearing some filters or lowering the match score slider.</p>
      </div>
    `;
    lucide.createIcons();
    return;
  }

  const bookmarks = getLocalBookmarks();
  const appliedList = getLocalApplied();
  const omitted = getLocalOmitted();

  container.innerHTML = filteredJobs.map((job) => {
    const evalData = job.evaluation || {};
    const score = evalData.match_score || 0;
    const portal = PORTAL_META[job.source] || { label: job.source, class: 'bg-slate-800 text-slate-300' };
    const isOmitted = Boolean(omitted[job.id]) || job.user_status === 'OMITTED';
    const isApplied = Boolean(appliedList[job.id]) || job.user_status === 'APPLIED';
    const isBookmarked = (Boolean(bookmarks[job.id]) || job.user_status === 'BOOKMARKED') && !isOmitted && !isApplied;

    // Score color styling
    let scoreBadgeClass = "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";
    if (score < 70) scoreBadgeClass = "bg-slate-700 text-slate-300 border-slate-600";
    else if (score < 85) scoreBadgeClass = "bg-amber-500/15 text-amber-400 border-amber-500/30";

    // Matching Skills Chips (up to 4)
    const skillsList = evalData.matching_skills || [];
    const skillsHtml = skillsList.slice(0, 4).map(skill => 
      `<span class="text-[10px] px-2 py-0.5 rounded-md bg-dark-hover text-slate-300 font-medium border border-dark-border/60">${escapeHtml(skill)}</span>`
    ).join('');

    return `
      <div class="bg-dark-card border border-dark-border rounded-xl p-4 flex flex-col justify-between hover:border-brand-500/40 hover:shadow-lg hover:shadow-brand-500/5 transition group">
        <div>
          <!-- Badges Top Row -->
          <div class="flex items-center justify-between gap-2 mb-2.5">
            <div class="flex items-center gap-1.5 flex-wrap">
              <span class="text-[11px] px-2.5 py-0.5 rounded-full font-bold border ${scoreBadgeClass}">
                ${score}% Fit
              </span>
              <span class="text-[10px] px-2.5 py-0.5 rounded-full font-medium border ${portal.class}">
                ${portal.label}
              </span>
            </div>
            
            <!-- Quick Actions: Bookmark, Applied Tick, Omit -->
            <div class="flex items-center gap-1">
              <button onclick="toggleBookmark('${job.id}')" title="${isBookmarked ? 'Remove bookmark' : 'Bookmark job'}" class="p-1.5 rounded-lg text-slate-400 hover:text-amber-400 hover:bg-amber-500/10 transition">
                <i data-lucide="star" class="w-4 h-4 ${isBookmarked ? 'fill-amber-400 text-amber-400' : ''}"></i>
              </button>
              <button onclick="toggleApplied('${job.id}')" title="${isApplied ? 'Applied (Click to unmark)' : 'Mark as Applied'}" class="p-1.5 rounded-lg transition ${isApplied ? 'text-emerald-400 bg-emerald-500/15 border border-emerald-500/30' : 'text-slate-400 hover:text-emerald-400 hover:bg-emerald-500/10 border border-transparent'}">
                <i data-lucide="check-circle" class="w-4 h-4 ${isApplied ? 'fill-emerald-400/20 text-emerald-400' : ''}"></i>
              </button>
              <button onclick="toggleOmit('${job.id}')" title="${isOmitted ? 'Omitted (Click to restore)' : 'Omit job'}" class="p-1.5 rounded-lg transition ${isOmitted ? 'text-rose-400 bg-rose-500/15 border border-rose-500/30' : 'text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 border border-transparent'}">
                <i data-lucide="eye-off" class="w-4 h-4 ${isOmitted ? 'fill-rose-400/20 text-rose-400' : ''}"></i>
              </button>
            </div>
          </div>

          <!-- Title & Company -->
          <h3 class="text-sm font-bold text-white group-hover:text-brand-400 transition tracking-tight line-clamp-1 mb-1">
            ${escapeHtml(job.title)}
          </h3>
          <p class="text-xs text-slate-400 line-clamp-1 font-medium mb-2.5">
            ${escapeHtml(job.company)} • <span class="text-slate-500">${escapeHtml(job.location || 'Sri Lanka')}</span>
          </p>

          <!-- Skills Chips -->
          <div class="flex flex-wrap gap-1 mb-3">
            ${skillsHtml || '<span class="text-[10px] text-slate-500">Early-career SWE</span>'}
          </div>
        </div>

        <!-- Card Footer Actions -->
        <div class="pt-3 border-t border-dark-border/60 flex items-center justify-between gap-2">
          <div class="flex items-center gap-1.5 text-[11px] text-slate-400">
            <span class="px-2 py-0.5 rounded bg-[#090d16] text-[10px] text-slate-400 font-medium">${escapeHtml(job.workplace_type || 'On-site')}</span>
            ${isApplied ? '<span class="text-emerald-400 font-semibold flex items-center gap-1 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20 text-[10px]"><i data-lucide="check" class="w-3 h-3"></i> Applied</span>' : ''}
            ${isOmitted ? '<span class="text-rose-400 font-semibold flex items-center gap-1 bg-rose-500/10 px-2 py-0.5 rounded border border-rose-500/20 text-[10px]"><i data-lucide="eye-off" class="w-3 h-3"></i> Omitted</span>' : ''}
          </div>
          
          <div class="flex items-center gap-1.5">
            <button onclick="openJobModal('${job.id}')" class="text-xs bg-dark-hover hover:bg-slate-700 text-slate-200 font-medium px-2.5 py-1.5 rounded-lg border border-dark-border transition">
              Details
            </button>
            <a href="${job.apply_url}" target="_blank" rel="noopener noreferrer" class="text-xs bg-brand-600 hover:bg-brand-500 text-white font-semibold px-3 py-1.5 rounded-lg shadow-sm flex items-center gap-1 transition">
              <span>Apply</span>
              <i data-lucide="external-link" class="w-3 h-3"></i>
            </a>
          </div>
        </div>
      </div>
    `;
  }).join('');

  lucide.createIcons();
}

// Render Table (Desktop)
function renderTable() {
  const tbody = document.getElementById('tableBody');
  if (!tbody) return;

  const bookmarks = getLocalBookmarks();
  const appliedList = getLocalApplied();
  const omitted = getLocalOmitted();

  tbody.innerHTML = filteredJobs.map((job) => {
    const evalData = job.evaluation || {};
    const score = evalData.match_score || 0;
    const portal = PORTAL_META[job.source] || { label: job.source };
    const isOmitted = Boolean(omitted[job.id]) || job.user_status === 'OMITTED';
    const isApplied = Boolean(appliedList[job.id]) || job.user_status === 'APPLIED';
    const isBookmarked = (Boolean(bookmarks[job.id]) || job.user_status === 'BOOKMARKED') && !isOmitted && !isApplied;

    return `
      <tr class="hover:bg-dark-hover/40 transition">
        <td class="py-3 px-4 font-bold ${score >= 85 ? 'text-emerald-400' : (score >= 70 ? 'text-amber-400' : 'text-slate-400')}">${score}%</td>
        <td class="py-3 px-4 font-semibold text-white">${escapeHtml(job.title)}</td>
        <td class="py-3 px-4 text-slate-300">${escapeHtml(job.company)}</td>
        <td class="py-3 px-4"><span class="px-2 py-0.5 rounded text-[10px] ${portal.class || 'bg-slate-800'}">${portal.label}</span></td>
        <td class="py-3 px-4 text-slate-400">${escapeHtml(job.location)} (${escapeHtml(job.workplace_type)})</td>
        <td class="py-3 px-4 text-slate-300">
          <span class="px-2 py-0.5 rounded text-[10px] font-semibold ${isOmitted ? 'bg-rose-500/15 text-rose-400 border border-rose-500/30' : (isApplied ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' : (isBookmarked ? 'bg-amber-500/15 text-amber-400 border border-amber-500/30' : 'bg-slate-800 text-slate-400'))}">
            ${isOmitted ? 'OMITTED' : (isApplied ? 'APPLIED' : (isBookmarked ? 'BOOKMARKED' : escapeHtml(job.user_status || 'NEW')))}
          </span>
        </td>
        <td class="py-3 px-4 text-right space-x-1">
          <button onclick="toggleBookmark('${job.id}')" title="${isBookmarked ? 'Remove bookmark' : 'Bookmark job'}" class="p-1 rounded text-slate-400 hover:text-amber-400 hover:bg-amber-500/10 transition inline-flex items-center">
            <i data-lucide="star" class="w-3.5 h-3.5 ${isBookmarked ? 'fill-amber-400 text-amber-400' : ''}"></i>
          </button>
          <button onclick="toggleApplied('${job.id}')" title="${isApplied ? 'Applied (Click to unmark)' : 'Mark as Applied'}" class="p-1 rounded transition inline-flex items-center ${isApplied ? 'text-emerald-400 bg-emerald-500/15 border border-emerald-500/30' : 'text-slate-400 hover:text-emerald-400 hover:bg-emerald-500/10 border border-transparent'}">
            <i data-lucide="check-circle" class="w-3.5 h-3.5 ${isApplied ? 'fill-emerald-400/20 text-emerald-400' : ''}"></i>
          </button>
          <button onclick="toggleOmit('${job.id}')" title="${isOmitted ? 'Omitted (Click to restore)' : 'Omit job'}" class="p-1 rounded transition inline-flex items-center ${isOmitted ? 'text-rose-400 bg-rose-500/15 border border-rose-500/30' : 'text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 border border-transparent'}">
            <i data-lucide="eye-off" class="w-3.5 h-3.5 ${isOmitted ? 'fill-rose-400/20 text-rose-400' : ''}"></i>
          </button>
          <button onclick="openJobModal('${job.id}')" class="px-2 py-1 bg-dark-card border border-dark-border rounded text-xs text-slate-300 hover:text-white transition">View</button>
          <a href="${job.apply_url}" target="_blank" class="px-2.5 py-1 bg-brand-600 rounded text-xs text-white font-semibold hover:bg-brand-500 transition">Apply</a>
        </td>
      </tr>
    `;
  }).join('');
  lucide.createIcons();
}

// Open Detail Modal
function openJobModal(jobId) {
  const job = allJobs.find(j => j.id === jobId);
  if (!job) return;
  currentJobInModal = job;

  const evalData = job.evaluation || {};
  const score = evalData.match_score || 0;
  const portal = PORTAL_META[job.source] || { label: job.source, class: '' };

  document.getElementById('modalTitle').textContent = job.title;
  document.getElementById('modalCompany').textContent = `${job.company} • ${job.location || 'Sri Lanka'}`;
  document.getElementById('modalScoreBadge').textContent = `${score}% Match`;
  document.getElementById('modalPortalBadge').textContent = portal.label;
  document.getElementById('modalWorkplaceBadge').textContent = job.workplace_type || 'On-site';
  document.getElementById('modalAISummary').textContent = evalData.summary || 'Suitability for entry / associate software engineer.';
  document.getElementById('modalDescription').textContent = job.description || 'No additional job description text available. Apply directly through the portal URL.';
  document.getElementById('modalApplyLink').href = job.apply_url;

  // Matching Skills Chips
  const matchingContainer = document.getElementById('modalMatchingSkills');
  matchingContainer.innerHTML = (evalData.matching_skills || []).map(s => 
    `<span class="px-2.5 py-1 rounded-md bg-emerald-500/15 text-emerald-300 font-semibold text-[11px] border border-emerald-500/30">${escapeHtml(s)}</span>`
  ).join('') || '<span class="text-slate-500 text-xs">General Software Engineering</span>';

  // Missing Skills Chips
  const missingContainer = document.getElementById('modalMissingSkills');
  missingContainer.innerHTML = (evalData.missing_skills || []).map(s => 
    `<span class="px-2.5 py-1 rounded-md bg-amber-500/15 text-amber-300 font-medium text-[11px] border border-amber-500/30">${escapeHtml(s)}</span>`
  ).join('') || '<span class="text-slate-500 text-xs">None flagged</span>';

  // Tracker Fields
  document.getElementById('modalStatusSelect').value = job.user_status || 'NEW';
  document.getElementById('modalNotesInput').value = job.user_notes || '';

  // Show Modal
  const modal = document.getElementById('jobModal');
  modal.classList.remove('hidden');
  modal.classList.add('flex');
  lucide.createIcons();
}

function closeModal() {
  const modal = document.getElementById('jobModal');
  modal.classList.add('hidden');
  modal.classList.remove('flex');
  currentJobInModal = null;
}

// Save Tracker Updates
async function saveModalTracker() {
  if (!currentJobInModal) return;
  const newStatus = document.getElementById('modalStatusSelect').value;
  const newNotes = document.getElementById('modalNotesInput').value;

  currentJobInModal.user_status = newStatus;
  currentJobInModal.user_notes = newNotes;

  // If local API is available, sync to SQLite backend
  if (currentMode === 'api') {
    try {
      await fetch(`/api/jobs/${currentJobInModal.id}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus, notes: newNotes })
      });
    } catch (e) {
      console.warn('API status sync failed:', e);
    }
  }

  // Also persist in localStorage for offline resiliency
  const b = getLocalBookmarks();
  const a = getLocalApplied();
  const o = getLocalOmitted();
  if (newStatus === 'BOOKMARKED') {
    b[currentJobInModal.id] = true;
    delete a[currentJobInModal.id];
    delete o[currentJobInModal.id];
  } else if (newStatus === 'APPLIED') {
    a[currentJobInModal.id] = true;
    delete o[currentJobInModal.id];
  } else if (newStatus === 'OMITTED') {
    o[currentJobInModal.id] = true;
    delete a[currentJobInModal.id];
  } else {
    delete b[currentJobInModal.id];
    delete a[currentJobInModal.id];
    delete o[currentJobInModal.id];
  }
  setLocalBookmarks(b);
  setLocalApplied(a);
  setLocalOmitted(o);

  const n = getLocalNotes();
  n[currentJobInModal.id] = newNotes;
  setLocalNotes(n);

  applyFilters();
  closeModal();
}

// Quick Bookmark Toggle on Card
async function toggleBookmark(jobId) {
  const job = allJobs.find(j => j.id === jobId);
  if (!job) return;

  const b = getLocalBookmarks();
  const a = getLocalApplied();
  const o = getLocalOmitted();
  const isCurrentlyBookmarked = Boolean(b[jobId]) || job.user_status === 'BOOKMARKED';

  if (isCurrentlyBookmarked) {
    delete b[jobId];
    if (job.user_status === 'BOOKMARKED') {
      job.user_status = a[jobId] ? 'APPLIED' : (o[jobId] ? 'OMITTED' : 'NEW');
    }
  } else {
    b[jobId] = true;
    delete o[jobId]; // Bookmarking restores from omitted
    if (job.user_status !== 'APPLIED') {
      job.user_status = 'BOOKMARKED';
    }
  }
  setLocalBookmarks(b);
  setLocalOmitted(o);

  // API sync if in API mode
  if (currentMode === 'api') {
    try {
      await fetch(`/api/jobs/${jobId}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: job.user_status })
      });
    } catch (e) {}
  }

  applyFilters();
}

// Quick Applied Toggle on Card
async function toggleApplied(jobId) {
  const job = allJobs.find(j => j.id === jobId);
  if (!job) return;

  const a = getLocalApplied();
  const b = getLocalBookmarks();
  const o = getLocalOmitted();
  const isCurrentlyApplied = Boolean(a[jobId]) || job.user_status === 'APPLIED';

  if (isCurrentlyApplied) {
    delete a[jobId];
    job.user_status = b[jobId] ? 'BOOKMARKED' : 'NEW';
  } else {
    a[jobId] = true;
    delete o[jobId]; // Cannot be both applied and omitted
    job.user_status = 'APPLIED';
  }
  setLocalApplied(a);
  setLocalOmitted(o);

  // API sync if in API mode
  if (currentMode === 'api') {
    try {
      await fetch(`/api/jobs/${jobId}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: job.user_status })
      });
    } catch (e) {}
  }

  applyFilters();
}

// Quick Omit Toggle on Card / Table
async function toggleOmit(jobId) {
  const job = allJobs.find(j => j.id === jobId);
  if (!job) return;

  const o = getLocalOmitted();
  const a = getLocalApplied();
  const b = getLocalBookmarks();
  const isCurrentlyOmitted = Boolean(o[jobId]) || job.user_status === 'OMITTED';

  if (isCurrentlyOmitted) {
    // Un-omit: restore back to bookmarked (if previously bookmarked) or NEW
    delete o[jobId];
    job.user_status = b[jobId] ? 'BOOKMARKED' : 'NEW';
  } else {
    // Mark as omitted: remove from applied, set as OMITTED
    o[jobId] = true;
    delete a[jobId];
    job.user_status = 'OMITTED';
  }
  setLocalOmitted(o);
  setLocalApplied(a);

  // API sync if in API mode
  if (currentMode === 'api') {
    try {
      await fetch(`/api/jobs/${jobId}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: job.user_status })
      });
    } catch (e) {}
  }

  applyFilters();
}

// Export CSV
function exportToCSV() {
  if (!filteredJobs.length) {
    alert('No jobs to export.');
    return;
  }

  const headers = ['Title', 'Company', 'Portal', 'Location', 'Workplace', 'Score', 'Status', 'Apply URL'];
  const rows = filteredJobs.map(j => [
    `"${(j.title || '').replace(/"/g, '""')}"`,
    `"${(j.company || '').replace(/"/g, '""')}"`,
    `"${j.source || ''}"`,
    `"${(j.location || '').replace(/"/g, '""')}"`,
    `"${j.workplace_type || ''}"`,
    j.evaluation?.match_score || 0,
    `"${j.user_status || 'NEW'}"`,
    `"${j.apply_url || ''}"`
  ]);

  const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
  const encodedUri = encodeURI(csvContent);
  const link = document.createElement('a');
  link.setAttribute('href', encodedUri);
  link.setAttribute('download', `software_engineering_jobs_${new Date().toISOString().slice(0, 10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

// HTML Escaping Utility
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
