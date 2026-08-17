// State Management
let currentState = {
    activePanel: "dashboard",
    appointmentsPage: 1,
    appointmentsLimit: 10,
    patientsPage: 1,
    patientsLimit: 10,
    doctors: [],
    syncInterval: null,
    
    // Patient delete context
    deleteTargetName: "",
    deleteTargetMobile: "",

    // Doctor delete context
    deleteTargetDoctorId: "",
    deleteTargetDoctorName: ""
};

// API Endpoints Prefix
const API_PREFIX = "/api/v1";

// ---- Supabase realtime setup ----
let supabaseClient = null;
let supabaseChannel = null;

function readSupabaseFromMeta() {
    try {
        if (!window.SUPABASE_URL) {
            const m = document.querySelector('meta[name="supabase-url"]');
            if (m && m.content) window.SUPABASE_URL = m.content;
        }
        if (!window.SUPABASE_KEY) {
            const k = document.querySelector('meta[name="supabase-key"]');
            if (k && k.content) window.SUPABASE_KEY = k.content;
        }
    } catch (e) {
        console.warn('[Supabase] reading meta tags failed', e);
    }
}

function initSupabaseClient() {
    readSupabaseFromMeta();

    if (!window.SUPABASE_URL || !window.SUPABASE_KEY) {
        console.warn('[Supabase] SUPABASE_URL or SUPABASE_KEY not set; realtime disabled.');
        return;
    }

    try {
        // `supabase` global is provided by the CDN UMD bundle included in index.html
        supabaseClient = (typeof supabase !== 'undefined')
            ? supabase.createClient(window.SUPABASE_URL, window.SUPABASE_KEY, { realtime: { params: { eventsPerSecond: 10 } } })
            : null;

        if (supabaseClient) console.log('[Supabase] client initialized');
        else console.warn('[Supabase] supabase UMD not found on window');
    } catch (err) {
        console.error('[Supabase] failed to initialize client', err);
        supabaseClient = null;
    }
}

function setupSupabaseRealtime() {
    if (!supabaseClient) return;

    try {
        // Clean up existing channel if present
        if (supabaseChannel) {
            try { supabaseClient.removeChannel(supabaseChannel); } catch(e){ /* ignore */ }
            supabaseChannel = null;
        }

        supabaseChannel = supabaseClient
            .channel('public:dashboard-changes')
            .on('postgres_changes', { event: '*', schema: 'public', table: 'appointments' }, payload => {
                logger('[supabase] appointments change', payload);
                // lightweight refresh for list views
                fetchRecentAppointments();
                fetchAppointments();
            })
            .on('postgres_changes', { event: '*', schema: 'public', table: 'doctors' }, payload => {
                logger('[supabase] doctors change', payload);
                fetchDoctorsList();
            })
            .on('postgres_changes', { event: '*', schema: 'public', table: 'patients' }, payload => {
                logger('[supabase] patients change', payload);
                fetchPatients();
            })
            .subscribe(({ status, error }) => {
                console.log('[supabase] subscription status:', status, error || '');
                if (status === 'SUBSCRIBED') {
                    showToast('Realtime connected');
                }
                if (error) {
                    console.error('[supabase] subscription error:', error);
                }
            });

    } catch (err) {
        console.error('[Supabase] failed to setup realtime', err);
    }
}

// ---- end Supabase realtime setup ----

// DOM Elements Mappings
const DOM = {
    // Navigation & Global UI
    navItems: document.querySelectorAll(".nav-item"),
    panels: document.querySelectorAll(".panel"),
    pageTitle: document.getElementById("page-title"),
    liveDate: document.getElementById("live-date"),
    refreshBtn: document.getElementById("refresh-btn"),
    themeToggleBtn: document.getElementById("theme-toggle-btn"),
    loadingSpinner: document.getElementById("loading-spinner"),
    
    // Toast alert
    toastAlert: document.getElementById("toast-alert"),
    toastMessage: document.getElementById("toast-message"),
    
    // Stats Elements
    statToday: document.getElementById("stat-today"),
    statUpcoming: document.getElementById("stat-upcoming"),
    statCancelled: document.getElementById("stat-cancelled"),
    statCompleted: document.getElementById("stat-completed"),
    statPatients: document.getElementById("stat-patients"),
    statRevenue: document.getElementById("stat-revenue"),
    statDoctors: document.getElementById("stat-doctors"),
    
    // Dashboard Panel Elements
    recentTableBody: document.querySelector("#recent-table tbody"),
    recentEmpty: document.getElementById("recent-empty"),
    viewAllApptsBtn: document.getElementById("view-all-appts-btn"),
    
    // Appointments Panel Elements
    appointmentsTableBody: document.querySelector("#appointments-table tbody"),
    appointmentsEmpty: document.getElementById("appointments-empty"),
    searchInput: document.getElementById("search-input"),
    filterDoctor: document.getElementById("filter-doctor"),
    filterDept: document.getElementById("filter-dept"),
    filterDate: document.getElementById("filter-date"),
    filterStatus: document.getElementById("filter-status"),
    resetFiltersBtn: document.getElementById("reset-filters-btn"),
    prevPageBtn: document.getElementById("prev-page-btn"),
    nextPageBtn: document.getElementById("next-page-btn"),
    pageIndicator: document.getElementById("page-indicator"),

    // Patients Panel Elements
    patientsTableBody: document.querySelector("#patients-table tbody"),
    patientsEmpty: document.getElementById("patients-empty"),
    patientSearchInput: document.getElementById("patient-search-input"),
    resetPatientFiltersBtn: document.getElementById("reset-patient-filters-btn"),
    patientPrevPageBtn: document.getElementById("patient-prev-page-btn"),
    patientNextPageBtn: document.getElementById("patient-next-page-btn"),
    patientPageIndicator: document.getElementById("patient-page-indicator"),
    
    // Doctors Panel Elements
    doctorsCardsGrid: document.getElementById("doctors-cards-grid"),
    
    // Settings Panel Elements (Editable Form)
    hospitalSettingsForm: document.getElementById("hospital-settings-form"),
    settingInputName: document.getElementById("setting-input-name"),
    settingInputOpening: document.getElementById("setting-input-opening"),
    settingInputClosing: document.getElementById("setting-input-closing"),
    settingInputEmergency: document.getElementById("setting-input-emergency"),
    settingInputPhone: document.getElementById("setting-input-phone"),
    settingInputAddress: document.getElementById("setting-input-address"),
    settingInputInsurance: document.getElementById("setting-input-insurance"),
    settingFeatures: document.getElementById("setting-features"),
    
    // Detail Modal Elements
    detailModal: document.getElementById("detail-modal"),
    closeModalBtn: document.getElementById("close-modal-btn"),
    detId: document.getElementById("det-id"),
    detStatus: document.getElementById("det-status"),
    detPatient: document.getElementById("det-patient"),
    detMobile: document.getElementById("det-mobile"),
    detDoctor: document.getElementById("det-doctor"),
    detDept: document.getElementById("det-dept"),
    detDate: document.getElementById("det-date"),
    detTime: document.getElementById("det-time"),
    detCreated: document.getElementById("det-created"),
    detUpdated: document.getElementById("det-updated"),
    detCancelled: document.getElementById("det-cancelled"),

    // Confirm Delete Patient Modal Elements
    confirmModal: document.getElementById("confirm-modal"),
    closeConfirmBtn: document.getElementById("close-confirm-btn"),
    cancelDeleteBtn: document.getElementById("cancel-delete-btn"),
    confirmDeleteBtn: document.getElementById("confirm-delete-btn"),
    confirmPatientName: document.getElementById("confirm-patient-name"),
    confirmPatientMobile: document.getElementById("confirm-patient-mobile"),

    // Edit Doctor Modal Form
    editDoctorModal: document.getElementById("edit-doctor-modal"),
    closeEditDoctorBtn: document.getElementById("close-edit-doctor-btn"),
    cancelEditDoctorBtn: document.getElementById("cancel-edit-doctor-btn"),
    editDoctorForm: document.getElementById("edit-doctor-form"),
    editDocId: document.getElementById("edit-doc-id"),
    editDocName: document.getElementById("edit-doc-name"),
    editDocDept: document.getElementById("edit-doc-dept"),
    editDocDays: document.getElementById("edit-doc-days"),
    editDocStart: document.getElementById("edit-doc-start"),
    editDocEnd: document.getElementById("edit-doc-end"),
    editDocDuration: document.getElementById("edit-doc-duration"),

    // Confirm Delete Doctor Modal Elements
    docConfirmModal: document.getElementById("doc-confirm-modal"),
    closeDocConfirmBtn: document.getElementById("close-doc-confirm-btn"),
    cancelDocDeleteBtn: document.getElementById("cancel-doc-delete-btn"),
    confirmDocDeleteBtn: document.getElementById("confirm-doc-delete-btn"),
    docConfirmName: document.getElementById("doc-confirm-name"),
    docConfirmId: document.getElementById("doc-confirm-id")
};

// Initialize Application
document.addEventListener("DOMContentLoaded", () => {
    initializeTheme();
    updateLiveDate();
    setupEventListeners();
    loadAllData(true);
    // Initialize Supabase realtime after initial load
    initSupabaseClient();
    setupSupabaseRealtime();
    startAutoRefresh();
});

// Theme Initialization
function initializeTheme() {
    const savedTheme = localStorage.getItem("theme") || "light";
    if (savedTheme === "dark") {
        document.body.classList.remove("light-theme");
        document.body.classList.add("dark-theme");
        DOM.themeToggleBtn.innerHTML = '<i class="fa-solid fa-sun"></i>';
    } else {
        document.body.classList.remove("dark-theme");
        document.body.classList.add("light-theme");
        DOM.themeToggleBtn.innerHTML = '<i class="fa-solid fa-moon"></i>';
    }
}

// Toggle Theme
function toggleTheme() {
    if (document.body.classList.contains("dark-theme")) {
        document.body.classList.remove("dark-theme");
        document.body.classList.add("light-theme");
        DOM.themeToggleBtn.innerHTML = '<i class="fa-solid fa-moon"></i>';
        localStorage.setItem("theme", "light");
        showToast("Switched to Light Theme");
    } else {
        document.body.classList.remove("light-theme");
        document.body.classList.add("dark-theme");
        DOM.themeToggleBtn.innerHTML = '<i class="fa-solid fa-sun"></i>';
        localStorage.setItem("theme", "dark");
        showToast("Switched to Dark Theme");
    }
}

// Update Live Date display in header
function updateLiveDate() {
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    DOM.liveDate.textContent = new Date().toLocaleDateString('en-US', options);
}

// Show/Hide Global Spinner
function showSpinner() {
    DOM.loadingSpinner.classList.remove("hidden");
}
function hideSpinner() {
    DOM.loadingSpinner.classList.add("hidden");
}

// Show Alert Toast Notification
function showToast(message) {
    DOM.toastMessage.textContent = message;
    DOM.toastAlert.classList.remove("hidden");
    setTimeout(() => {
        DOM.toastAlert.classList.add("hidden");
    }, 4000);
}

// Start Auto Refresh Loop (Every 10 seconds)
function startAutoRefresh() {
    if (currentState.syncInterval) {
        clearInterval(currentState.syncInterval);
    }
    currentState.syncInterval = setInterval(() => {
        logger("Auto sync dashboard refreshing state...");
        loadAllData(false); // Silent sync refresh
    }, 10000);
}

// Log utility
function logger(msg, data = "") {
    console.log(`[Dashboard] ${msg}`, data);
}

// Pull Dashboard operations
async function loadAllData(displayLoading = true) {
    if (displayLoading) showSpinner();
    try {
        await Promise.all([
            fetchStats(),
            fetchDoctorsList(),
            fetchRecentAppointments(),
            fetchAppointments(),
            fetchPatients(),
            fetchAiCapabilities()
        ]);
    } catch (err) {
        console.error("Error pulling panel data:", err);
    } finally {
        if (displayLoading) hideSpinner();
    }
}

// ----------------------------------------------------
// API REQUEST CHANNELS
// ----------------------------------------------------

// 1. Fetch stats card counters
async function fetchStats() {
    try {
        const res = await fetch(`${API_PREFIX}/dashboard/stats`);
        const json = await res.json();
        if (json.success) {
            const data = json.data;
            DOM.statToday.textContent = data.today_appointments;
            DOM.statUpcoming.textContent = data.upcoming_appointments;
            DOM.statCancelled.textContent = data.cancelled_appointments;
            DOM.statCompleted.textContent = data.completed_appointments;
            DOM.statPatients.textContent = data.total_patients;
            DOM.statRevenue.textContent = `$${data.estimated_revenue.toLocaleString()}`;
            DOM.statDoctors.textContent = data.total_doctors;
        }
    } catch (err) {
        logger("Failed to fetch statistics cards counters.", err);
    }
}

// 2. Fetch Doctors List (for filter select and doctors grid)
async function fetchDoctorsList() {
    try {
        const res = await fetch(`${API_PREFIX}/dashboard/doctors`);
        const json = await res.json();
        if (json.success) {
            currentState.doctors = json.data;
            populateDoctorFilters(json.data);
            renderDoctorsGrid(json.data);
        }
    } catch (err) {
        logger("Failed to load doctors list.", err);
    }
}

function populateDoctorFilters(doctors) {
    DOM.filterDoctor.innerHTML = '<option value="">All Doctors</option>';
    doctors.forEach(doc => {
        const opt = document.createElement("option");
        opt.value = doc.doctor_id;
        opt.textContent = doc.doctor_name;
        DOM.filterDoctor.appendChild(opt);
    });
}

function renderDoctorsGrid(doctors) {
    DOM.doctorsCardsGrid.innerHTML = "";
    if (doctors.length === 0) {
        DOM.doctorsCardsGrid.innerHTML = '<div class="empty-state"><i class="fa-solid fa-user-doctor"></i><p>No active doctor profiles on call</p></div>';
        return;
    }

    doctors.forEach(doc => {
        const card = document.createElement("div");
        card.className = "doctor-card";
        card.innerHTML = `
            <div class="doctor-card-header">
                <div class="doctor-card-info-wrap">
                    <div class="doctor-avatar">
                        <i class="fa-solid fa-stethoscope"></i>
                    </div>
                    <div class="doctor-title">
                        <h3>${doc.doctor_name}</h3>
                        <span>${doc.department}</span>
                    </div>
                </div>
            </div>
            <div class="doctor-schedule-list">
                <div class="schedule-item">
                    <span class="schedule-label">Doctor ID</span>
                    <span class="schedule-val">${doc.doctor_id}</span>
                </div>
                <div class="schedule-item">
                    <span class="schedule-label">Working hours</span>
                    <span class="schedule-val">${doc.start_time} - ${doc.end_time}</span>
                </div>
                <div class="schedule-item">
                    <span class="schedule-label">Slot Duration</span>
                    <span class="schedule-val">${doc.slot_duration} minutes</span>
                </div>
                <div class="schedule-item">
                    <span class="schedule-label">Available Days</span>
                    <span class="schedule-val">${doc.available_days}</span>
                </div>
            </div>
            <div class="doctor-card-actions">
                <button class="btn btn-secondary" style="padding:6px 12px; font-size:12px; border-radius:6px; box-shadow:none;" onclick="triggerEditDoctor('${doc.doctor_id}')">
                    <i class="fa-solid fa-edit"></i> Edit
                </button>
                <button class="btn" style="padding:6px 12px; font-size:12px; border-radius:6px; background-color:var(--danger); color:white; box-shadow:none;" onclick="triggerDeleteDoctor('${doc.doctor_id}','${(doc.doctor_name||'').replace(/'/g,"\\'")}")">
                    <i class="fa-solid fa-trash-can"></i> Delete
                </button>
            </div>
        `;
        DOM.doctorsCardsGrid.appendChild(card);
    });
}

// 3. Fetch Recent Appointments list
async function fetchRecentAppointments() {
    try {
        const res = await fetch(`${API_PREFIX}/dashboard/recent`);
        const json = await res.json();
        if (json.success) {
            renderRecentTable(json.data);
        }
    } catch (err) {
        logger("Failed to load recent appointments list.", err);
    }
}

function renderRecentTable(appointments) {
    DOM.recentTableBody.innerHTML = "";
    if (appointments.length === 0) {
        DOM.recentEmpty.classList.remove("hidden");
        return;
    }
    DOM.recentEmpty.classList.add("hidden");

    appointments.forEach(appt => {
        const row = document.createElement("tr");
        row.style.cursor = "pointer";
        row.addEventListener("click", () => showAppointmentDetail(appt.appointment_id));
        
        row.innerHTML = `
            <td><strong>#${appt.appointment_id}</strong></td>
            <td>${appt.patient_name}</td>
            <td>${appt.mobile}</td>
            <td>${appt.doctor_name}</td>
            <td>${appt.department}</td>
            <td>${appt.appointment_date}</td>
            <td>${appt.appointment_time}</td>
            <td><span class="badge ${getStatusBadgeClass(appt.status)}">${appt.status}</span></td>
        `;
        DOM.recentTableBody.appendChild(row);
    });
}

function getStatusBadgeClass(status) {
    const s = (status || '').toLowerCase();
    if (s === "booked") return "badge-booked";
    if (s === "cancelled") return "badge-cancelled";
    if (s === "rescheduled") return "badge-rescheduled";
    return "badge-completed";
}

// 4. Fetch Paginated & Filtered Appointments List
async function fetchAppointments() {
    const page = currentState.appointmentsPage;
    const limit = currentState.appointmentsLimit;
    const search = DOM.searchInput.value.trim();
    const doctorId = DOM.filterDoctor.value;
    const dept = DOM.filterDept.value;
    const date = DOM.filterDate.value;
    const status = DOM.filterStatus.value;

    let url = `${API_PREFIX}/dashboard/appointments?page=${page}&limit=${limit}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    if (doctorId) url += `&doctor_id=${encodeURIComponent(doctorId)}`;
    if (dept) url += `&department=${encodeURIComponent(dept)}`;
    if (date) url += `&date=${encodeURIComponent(date)}`;
    if (status) url += `&status=${encodeURIComponent(status)}`;

    try {
        const res = await fetch(url);
        const json = await res.json();
        if (json.success) {
            renderAppointmentsTable(json.data.appointments);
            updatePaginationControls(json.data);
        }
    } catch (err) {
        logger("Failed to query appointments list.", err);
    }
}

function renderAppointmentsTable(appointments) {
    DOM.appointmentsTableBody.innerHTML = "";
    if (appointments.length === 0) {
        DOM.appointmentsEmpty.classList.remove("hidden");
        DOM.prevPageBtn.disabled = true;
        DOM.nextPageBtn.disabled = true;
        DOM.pageIndicator.textContent = "Page 1 of 1";
        return;
    }
    DOM.appointmentsEmpty.classList.add("hidden");

    appointments.forEach(appt => {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td><strong>#${appt.appointment_id}</strong></td>
            <td>${appt.patient_name}</td>
            <td>${appt.mobile}</td>
            <td>${appt.doctor_name}</td>
            <td>${appt.department}</td>
            <td>${appt.appointment_date}</td>
            <td>${appt.appointment_time}</td>
            <td><span class="badge ${getStatusBadgeClass(appt.status)}">${appt.status}</span></td>
            <td><span style="font-size:11.5px; color:var(--text-secondary);">${appt.created_at || "-"}</span></td>
            <td>
                <button class="action-icon-btn" onclick="showAppointmentDetail('${appt.appointment_id}')" title="View details">
                    <i class="fa-solid fa-eye"></i>
                </button>
            </td>
        `;
        DOM.appointmentsTableBody.appendChild(row);
    });
}

function updatePaginationControls(pageData) {
    const page = pageData.page;
    const totalPages = pageData.total_pages;

    DOM.pageIndicator.textContent = `Page ${page} of ${totalPages || 1}`;
    DOM.prevPageBtn.disabled = page <= 1;
    DOM.nextPageBtn.disabled = page >= totalPages;
}

// 5. Fetch unique patients directory list
async function fetchPatients() {
    const page = currentState.patientsPage;
    const limit = currentState.patientsLimit;
    const search = DOM.patientSearchInput.value.trim();

    let url = `${API_PREFIX}/dashboard/patients?page=${page}&limit=${limit}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;

    try {
        const res = await fetch(url);
        const json = await res.json();
        if (json.success) {
            renderPatientsTable(json.data.patients);
            updatePatientPaginationControls(json.data);
        }
    } catch (err) {
        logger("Failed to query unique patients list.", err);
    }
}

function renderPatientsTable(patients) {
    DOM.patientsTableBody.innerHTML = "";
    if (patients.length === 0) {
        DOM.patientsEmpty.classList.remove("hidden");
        DOM.patientPrevPageBtn.disabled = true;
        DOM.patientNextPageBtn.disabled = true;
        DOM.patientPageIndicator.textContent = "Page 1 of 1";
        return;
    }
    DOM.patientsEmpty.classList.add("hidden");

    patients.forEach(p => {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td><strong>${p.patient_name}</strong></td>
            <td>${p.mobile}</td>
            <td>${p.total_appointments}</td>
            <td>${p.last_visit}</td>
            <td><span class="badge ${p.status === 'Active' ? 'badge-active' : 'badge-regular'}">${p.status}</span></td>
            <td>
                <button class="action-icon-btn btn-delete" onclick="triggerDeletePatient('${p.patient_name.replace(/'/g, "\\'")}', '${p.mobile}')" title="Delete patient and cancel all bookings">
                    <i class="fa-solid fa-trash-can"></i>
                </button>
            </td>
        `;
        DOM.patientsTableBody.appendChild(row);
    });
}

function updatePatientPaginationControls(pageData) {
    const page = pageData.page;
    const totalPages = pageData.total_pages;

    DOM.patientPageIndicator.textContent = `Page ${page} of ${totalPages || 1}`;
    DOM.patientPrevPageBtn.disabled = page <= 1;
    DOM.patientNextPageBtn.disabled = page >= totalPages;
}

// 6. Delete Patient Operations
function triggerDeletePatient(name, mobile) {
    currentState.deleteTargetName = name;
    currentState.deleteTargetMobile = mobile;
    
    DOM.confirmPatientName.textContent = name;
    DOM.confirmPatientMobile.textContent = mobile;
    DOM.confirmModal.classList.remove("hidden");
}

async function executeDeletePatient() {
    showSpinner();
    closeConfirmModal();
    const name = currentState.deleteTargetName;
    const mobile = currentState.deleteTargetMobile;

    try {
        const res = await fetch(`${API_PREFIX}/dashboard/patient?patient_name=${encodeURIComponent(name)}&mobile=${encodeURIComponent(mobile)}`, {
            method: 'DELETE'
        });
        const json = await res.json();
        if (json.success) {
            showToast(`Patient '${name}' deleted successfully.`);
            loadAllData(false);
        } else {
            alert(`Error: ${json.message}`);
        }
    } catch (err) {
        console.error("Failed to perform patient deletion:", err);
        alert("Failed to delete patient. Please try again.");
    } finally {
        hideSpinner();
    }
}

function closeConfirmModal() {
    DOM.confirmModal.classList.add("hidden");
}

// 7. Doctor Edit Modal Actions [NEW]
function triggerEditDoctor(docId) {
    const doctor = currentState.doctors.find(d => d.doctor_id === docId);
    if (!doctor) {
        alert("Doctor details not loaded yet.");
        return;
    }

    DOM.editDocId.value = doctor.doctor_id;
    DOM.editDocName.value = doctor.doctor_name;
    DOM.editDocDept.value = doctor.department;
    DOM.editDocDays.value = doctor.available_days;
    DOM.editDocStart.value = doctor.start_time;
    DOM.editDocEnd.value = doctor.end_time;
    DOM.editDocDuration.value = doctor.slot_duration;

    DOM.editDoctorModal.classList.remove("hidden");
}

function closeEditDoctorModal() {
    DOM.editDoctorModal.classList.add("hidden");
}

async function saveDoctorDetails(e) {
    e.preventDefault();
    showSpinner();

    const payload = {
        doctor_id: DOM.editDocId.value,
        doctor_name: DOM.editDocName.value,
        department: DOM.editDocDept.value,
        available_days: DOM.editDocDays.value,
        start_time: DOM.editDocStart.value,
        end_time: DOM.editDocEnd.value,
        slot_duration: parseInt(DOM.editDocDuration.value)
    };

    try {
        const res = await fetch(`${API_PREFIX}/dashboard/doctor`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.success) {
            showToast(`Schedules for ${payload.doctor_name} updated successfully.`);
            closeEditDoctorModal();
            loadAllData(false);
        } else {
            alert(`Error: ${json.message}`);
        }
    } catch (err) {
        console.error("Failed to update doctor details:", err);
        alert("Failed to save changes. Please try again.");
    } finally {
        hideSpinner();
    }
}

// 8. Doctor Delete Modal Actions [NEW]
function triggerDeleteDoctor(docId, name) {
    currentState.deleteTargetDoctorId = docId;
    currentState.deleteTargetDoctorName = name;

    DOM.docConfirmName.textContent = name;
    DOM.docConfirmId.textContent = docId;
    DOM.docConfirmModal.classList.remove("hidden");
}

function closeDocConfirmModal() {
    DOM.docConfirmModal.classList.add("hidden");
}

async function executeDeleteDoctor() {
    showSpinner();
    closeDocConfirmModal();
    const docId = currentState.deleteTargetDoctorId;
    const name = currentState.deleteTargetDoctorName;

    try {
        const res = await fetch(`${API_PREFIX}/dashboard/doctor/${docId}`, {
            method: 'DELETE'
        });
        const json = await res.json();
        if (json.success) {
            showToast(`Doctor profile '${name}' and associated schedules deleted.`);
            loadAllData(false);
        } else {
            alert(`Error: ${json.message}`);
        }
    } catch (err) {
        console.error("Failed to delete doctor profile:", err);
        alert("Failed to remove doctor. Please try again.");
    } finally {
        hideSpinner();
    }
}

// 9. Fetch AI Capabilities (and populate settings form)
async function fetchAiCapabilities() {
    try {
        const res = await fetch(`${API_PREFIX}/ai-capabilities`);
        const json = await res.json();
        if (json.success) {
            const data = json.data;
            
            // Populate settings inputs
            DOM.settingInputName.value = data.hospital_name || "";
            DOM.settingInputEmergency.value = data.emergency_hours || "24 Hours";
            DOM.settingInputPhone.value = data.phone || "9876543210";
            DOM.settingInputAddress.value = data.address || "Visakhapatnam";
            DOM.settingInputInsurance.value = data.insurance || "Cash, UPI, Insurance";
            DOM.settingInputOpening.value = data.opening_time || "09:00";
            DOM.settingInputClosing.value = data.closing_time || "20:00";

            // Render features list tags
            DOM.settingFeatures.innerHTML = "";
            if (data.supported_features) {
                data.supported_features.forEach(feat => {
                    const tag = document.createElement("span");
                    tag.className = "feature-tag";
                    tag.textContent = feat.replace(/_/g, " ");
                    DOM.settingFeatures.appendChild(tag);
                });
            }
        }
    } catch (err) {
        logger("Failed to load AI system capabilities.", err);
    }
}

// 10. Update Hospital configurations [NEW]
async function saveHospitalSettings(e) {
    e.preventDefault();
    showSpinner();

    const payload = {
        "Hospital Name": DOM.settingInputName.value,
        "Opening Time": DOM.settingInputOpening.value,
        "Closing Time": DOM.settingInputClosing.value,
        "Emergency": DOM.settingInputEmergency.value,
        "Phone": DOM.settingInputPhone.value,
        "Address": DOM.settingInputAddress.value,
        "Insurance": DOM.settingInputInsurance.value
    };

    try {
        const res = await fetch(`${API_PREFIX}/dashboard/hospital-info`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.success) {
            showToast("Hospital configurations saved successfully.");
            loadAllData(false);
        } else {
            alert(`Error: ${json.message}`);
        }
    } catch (err) {
        console.error("Failed to save hospital settings:", err);
        alert("Failed to save hospital settings. Please try again.");
    } finally {
        hideSpinner();
    }
}

// 11. Fetch Single Appointment details deep-dive
async function showAppointmentDetail(appointmentId) {
    showSpinner();
    try {
        const res = await fetch(`${API_PREFIX}/dashboard/appointment/${appointmentId}`);
        const json = await res.json();
        if (json.success) {
            populateDetailModal(json.data);
            DOM.detailModal.classList.remove("hidden");
        } else {
            alert(`Error: ${json.message}`);
        }
    } catch (err) {
        console.error("Failed to load appointment details:", err);
        alert("Failed to load appointment record. Please try again.");
    } finally {
        hideSpinner();
    }
}

function populateDetailModal(data) {
    DOM.detId.textContent = `#${data.appointment_id}`;
    DOM.detStatus.innerHTML = `<span class="badge ${getStatusBadgeClass(data.status)}">${data.status}</span>`;
    DOM.detPatient.textContent = data.patient_name;
    DOM.detMobile.textContent = data.mobile;
    DOM.detDoctor.textContent = data.doctor_name;
    DOM.detDept.textContent = data.department;
    DOM.detDate.textContent = data.appointment_date;
    DOM.detTime.textContent = data.appointment_time;
    DOM.detCreated.textContent = data.created_at || "-";
    DOM.detUpdated.textContent = data.updated_at || "-";
    DOM.detCancelled.textContent = data.cancelled_at || "-";
}

function closeDetailModal() {
    DOM.detailModal.classList.add("hidden");
}

// ----------------------------------------------------
// EVENT LISTENERS BINDINGS
// ----------------------------------------------------

function setupEventListeners() {
    // Light/Dark Theme toggle btn
    DOM.themeToggleBtn.addEventListener("click", toggleTheme);

    // Sidebar Panel Toggle Items
    DOM.navItems.forEach(item => {
        item.addEventListener("click", () => {
            DOM.navItems.forEach(n => n.classList.remove("active"));
            item.classList.add("active");

            const targetPanel = item.getAttribute("data-target");
            DOM.panels.forEach(p => p.classList.remove("active"));
            document.getElementById(`panel-${targetPanel}`).classList.add("active");

            currentState.activePanel = targetPanel;
            DOM.pageTitle.textContent = getPanelTitle(targetPanel);
            
            if (targetPanel === "appointments") {
                fetchAppointments();
            } else if (targetPanel === "patients") {
                fetchPatients();
            } else if (targetPanel === "dashboard") {
                fetchRecentAppointments();
            }
        });
    });

    // Header force refresh btn
    DOM.refreshBtn.addEventListener("click", () => loadAllData(true));

    // Dashboard panel view-all btn
    DOM.viewAllApptsBtn.addEventListener("click", () => {
        const apptsTabItem = document.querySelector('[data-target="appointments"]');
        if (apptsTabItem) apptsTabItem.click();
    });

    // Close Modal triggers (Appointment detail)
    DOM.closeModalBtn.addEventListener("click", closeDetailModal);
    DOM.detailModal.addEventListener("click", (e) => {
        if (e.target === DOM.detailModal) closeDetailModal();
    });

    // Deletion Modal Dialog triggers (Patient)
    DOM.closeConfirmBtn.addEventListener("click", closeConfirmModal);
    DOM.cancelDeleteBtn.addEventListener("click", closeConfirmModal);
    DOM.confirmDeleteBtn.addEventListener("click", executeDeletePatient);
    DOM.confirmModal.addEventListener("click", (e) => {
        if (e.target === DOM.confirmModal) closeConfirmModal();
    });

    // Edit Doctor Modal Form triggers
    DOM.closeEditDoctorBtn.addEventListener("click", closeEditDoctorModal);
    DOM.cancelEditDoctorBtn.addEventListener("click", closeEditDoctorModal);
    DOM.editDoctorForm.addEventListener("submit", saveDoctorDetails);
    DOM.editDoctorModal.addEventListener("click", (e) => {
        if (e.target === DOM.editDoctorModal) closeEditDoctorModal();
    });

    // Deletion Modal Dialog triggers (Doctor)
    DOM.closeDocConfirmBtn.addEventListener("click", closeDocConfirmModal);
    DOM.cancelDocDeleteBtn.addEventListener("click", closeDocConfirmModal);
    DOM.confirmDocDeleteBtn.addEventListener("click", executeDeleteDoctor);
    DOM.docConfirmModal.addEventListener("click", (e) => {
        if (e.target === DOM.docConfirmModal) closeDocConfirmModal();
    });

    // Settings Submit Form Trigger
    DOM.hospitalSettingsForm.addEventListener("submit", saveHospitalSettings);

    // Reset Filters button (Appointments)
    DOM.resetFiltersBtn.addEventListener("click", () => {
        DOM.searchInput.value = "";
        DOM.filterDoctor.value = "";
        DOM.filterDept.value = "";
        DOM.filterDate.value = "";
        DOM.filterStatus.value = "";
        currentState.appointmentsPage = 1;
        fetchAppointments();
    });

    // Reset Filters button (Patients)
    DOM.resetPatientFiltersBtn.addEventListener("click", () => {
        DOM.patientSearchInput.value = "";
        currentState.patientsPage = 1;
        fetchPatients();
    });

    // Filter event listeners (Appointments)
    DOM.searchInput.addEventListener("input", debounce(() => {
        currentState.appointmentsPage = 1;
        fetchAppointments();
    }, 300));
    DOM.filterDoctor.addEventListener("change", () => {
        currentState.appointmentsPage = 1;
        fetchAppointments();
    });
    DOM.filterDept.addEventListener("change", () => {
        currentState.appointmentsPage = 1;
        fetchAppointments();
    });
    DOM.filterDate.addEventListener("change", () => {
        currentState.appointmentsPage = 1;
        fetchAppointments();
    });
    DOM.filterStatus.addEventListener("change", () => {
        currentState.appointmentsPage = 1;
        fetchAppointments();
    });

    // Filter event listeners (Patients)
    DOM.patientSearchInput.addEventListener("input", debounce(() => {
        currentState.patientsPage = 1;
        fetchPatients();
    }, 300));

    // Pagination Click events (Appointments)
    DOM.prevPageBtn.addEventListener("click", () => {
        if (currentState.appointmentsPage > 1) {
            currentState.appointmentsPage--;
            fetchAppointments();
        }
    });
    DOM.nextPageBtn.addEventListener("click", () => {
        currentState.appointmentsPage++;
        fetchAppointments();
    });

    // Pagination Click events (Patients)
    DOM.patientPrevPageBtn.addEventListener("click", () => {
        if (currentState.patientsPage > 1) {
            currentState.patientsPage--;
            fetchPatients();
        }
    });
    DOM.patientNextPageBtn.addEventListener("click", () => {
        currentState.patientsPage++;
        fetchPatients();
    });
}

function getPanelTitle(panelName) {
    if (panelName === "dashboard") return "Dashboard Overview";
    if (panelName === "appointments") return "Appointments Manager";
    if (panelName === "patients") return "Patients Directory";
    if (panelName === "doctors") return "Doctors Schedule Directory";
    return "AI Hospital Specifications Settings";
}

// Debounce helper
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Global mappings for HTML triggers
window.showAppointmentDetail = showAppointmentDetail;
window.triggerDeletePatient = triggerDeletePatient;
window.triggerEditDoctor = triggerEditDoctor;
window.triggerDeleteDoctor = triggerDeleteDoctor;
