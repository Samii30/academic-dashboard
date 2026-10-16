/**
 * AcademicTrack - Dashboard de Suivi Académique & Planning d'Études
 * Frontend JavaScript Vanilla (Fetch API, Modales, Chart.js & Simulateur)
 */

// État local en mémoire
let state = {
    modules: [],
    tasks: [],
    stats: null,
    chartMode: "averages" // 'averages' ou 'coefficients'
};

// Instance globale du graphique Chart.js
let academicChartInstance = null;

// Initialisation au chargement du DOM
document.addEventListener("DOMContentLoaded", () => {
    console.log("AcademicTrack v3.0 initialisé.");

    // Initialisation des données et de l'état
    checkBackendHealth();
    loadDashboardData();
    tryLoadWeeklySchedule();  // Affiche l'emploi du temps si des cours ont déjà été importés

    // Configuration des écouteurs d'événements
    setupModalListeners();
    setupFormListeners();
    setupSimulatorListeners();
    setupChartToggleListeners();

    // Rafraîchissement périodique de l'état du serveur
    setInterval(checkBackendHealth, 30000);
});

/* ==========================================================================
   Vérification de Santé API (Health Check)
   ========================================================================== */
async function checkBackendHealth() {
    const badge = document.getElementById("health-indicator");
    const textLabel = document.getElementById("health-text");
    const footerDbStatus = document.getElementById("footer-db-status");

    try {
        const response = await fetch("/api/health", {
            method: "GET",
            headers: { "Accept": "application/json" }
        });

        if (!response.ok) throw new Error(`HTTP Error: ${response.status}`);

        const data = await response.json();
        if (data.status === "ok") {
            badge.className = "health-badge connected";
            textLabel.textContent = "Backend connecté";
            if (footerDbStatus) {
                footerDbStatus.textContent = `DB: academic_dashboard.db (${data.database})`;
            }
        } else {
            badge.className = "health-badge error";
            textLabel.textContent = "Base dégradée";
        }
    } catch (error) {
        badge.className = "health-badge error";
        textLabel.textContent = "Serveur hors-ligne";
    }
}

/* ==========================================================================
   Chargement Global des Données (Modules, Tâches, Synthèse)
   ========================================================================== */
async function loadDashboardData() {
    await Promise.all([
        loadModules(),
        loadTasks(),
        loadStats()
    ]);

    // Mise à jour des composants dépendants
    renderAcademicChart();
    updateSimulatorModuleSelect();
    runSimulation();
}

/* ==========================================================================
   Gestion des Modules (UE)
   ========================================================================== */
async function loadModules() {
    const container = document.getElementById("modules-container");

    try {
        const response = await fetch("/api/modules");
        if (!response.ok) throw new Error("Erreur de récupération des modules");

        state.modules = await response.json();
        renderModules();
        updateGradeModuleSelect();
    } catch (error) {
        console.error("Erreur chargement modules:", error);
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">⚠️</div>
                <h3>Erreur de chargement</h3>
                <p>Impossible de charger vos modules. Veuillez rafraîchir la page.</p>
            </div>
        `;
    }
}

function renderModules() {
    const container = document.getElementById("modules-container");
    if (!state.modules || state.modules.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📚</div>
                <h3>Aucun module enregistré</h3>
                <p>Commencez par ajouter vos matières universitaires (UE) et leurs coefficients.</p>
                <button class="btn btn-primary btn-sm" onclick="openModal('modal-module')">
                    + Ajouter votre premier module
                </button>
            </div>
        `;
        return;
    }

    container.innerHTML = state.modules.map(module => {
        let averageHtml = `<span class="average-badge empty">-- / 20</span>`;
        if (module.average !== null && module.average !== undefined) {
            const isPassed = module.average >= 10.0;
            const badgeClass = isPassed ? "passed" : "failed";
            averageHtml = `<span class="average-badge ${badgeClass}">${module.average.toFixed(2)} / 20</span>`;
        }

        let gradesHtml = `<span class="empty-grades-text">Aucune note pour le moment.</span>`;
        if (module.grades && module.grades.length > 0) {
            gradesHtml = module.grades.map(grade => `
                <div class="grade-pill" title="Date: ${escapeHtml(grade.date)}">
                    <span>${escapeHtml(grade.intitule)}:</span>
                    <span class="grade-pill-note">${grade.note.toFixed(2)}/20</span>
                    <span class="grade-pill-coef">(coef ${grade.coefficient})</span>
                    <button class="grade-pill-del" onclick="deleteGrade(${grade.id})" title="Supprimer cette note">✕</button>
                </div>
            `).join("");
        }

        return `
            <div class="module-card" id="module-card-${module.id}">
                <div class="module-card-header">
                    <div class="module-info">
                        <div class="module-title-row">
                            <span class="module-code-badge">${escapeHtml(module.code)}</span>
                            <span class="module-name">${escapeHtml(module.nom)}</span>
                        </div>
                        <span class="module-meta">Coefficient : ${module.coefficient} • ${module.grades ? module.grades.length : 0} note(s)</span>
                    </div>

                    <div class="module-card-aside">
                        ${averageHtml}
                        <button class="btn btn-secondary btn-sm" onclick="openAddGradeForModule(${module.id})" title="Ajouter une note à ce module">
                            + Note
                        </button>
                        <button class="btn-icon" onclick="deleteModule(${module.id}, '${escapeHtml(module.code)}')" title="Supprimer ce module">
                            🗑️
                        </button>
                    </div>
                </div>

                <div class="module-grades-list">
                    ${gradesHtml}
                </div>
            </div>
        `;
    }).join("");
}

function updateGradeModuleSelect() {
    const gradeSelect = document.getElementById("grade-module-id");
    if (!gradeSelect) return;

    if (state.modules.length === 0) {
        gradeSelect.innerHTML = `<option value="">Aucun module disponible - Créez-en un d'abord</option>`;
        return;
    }

    gradeSelect.innerHTML = `<option value="">Sélectionnez un module...</option>` +
        state.modules.map(m => `<option value="${m.id}">${escapeHtml(m.code)} - ${escapeHtml(m.nom)}</option>`).join("");
}

async function deleteModule(moduleId, moduleCode) {
    if (!confirm(`Êtes-vous sûr de vouloir supprimer le module ${moduleCode} et toutes ses notes associées ?`)) {
        return;
    }

    try {
        const response = await fetch(`/api/modules/${moduleId}`, {
            method: "DELETE"
        });

        if (!response.ok) throw new Error("Échec de la suppression");

        showToast(`Module ${moduleCode} supprimé avec succès.`, "success");
        await loadDashboardData();
    } catch (error) {
        showToast("Erreur lors de la suppression du module.", "error");
    }
}

/* ==========================================================================
   Gestion des Notes (Grades)
   ========================================================================== */
function openAddGradeForModule(moduleId) {
    const gradeSelect = document.getElementById("grade-module-id");
    if (gradeSelect) {
        gradeSelect.value = moduleId;
    }
    openModal("modal-grade");
}

async function deleteGrade(gradeId) {
    if (!confirm("Voulez-vous supprimer cette note ?")) return;

    try {
        const response = await fetch(`/api/grades/${gradeId}`, {
            method: "DELETE"
        });

        if (!response.ok) throw new Error("Erreur de suppression de la note");

        showToast("Note supprimée.", "success");
        await loadDashboardData();
    } catch (error) {
        showToast("Impossible de supprimer la note.", "error");
    }
}

/* ==========================================================================
   Gestion des Tâches (Planning & Modification)
   ========================================================================== */
async function loadTasks() {
    const container = document.getElementById("tasks-container");

    try {
        const response = await fetch("/api/tasks");
        if (!response.ok) throw new Error("Erreur de récupération des tâches");

        state.tasks = await response.json();
        renderTasks();
    } catch (error) {
        console.error("Erreur chargement tâches:", error);
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">⚠️</div>
                <h3>Erreur de chargement</h3>
                <p>Impossible de charger vos tâches.</p>
            </div>
        `;
    }
}

function renderTasks() {
    const container = document.getElementById("tasks-container");
    if (!state.tasks || state.tasks.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">✨</div>
                <h3>Planning dégagé !</h3>
                <p>Aucune tâche en cours. Ajoutez un devoir, une révision ou un TP à préparer.</p>
                <button class="btn btn-primary btn-sm" onclick="openModal('modal-task')">
                    + Ajouter une tâche
                </button>
            </div>
        `;
        return;
    }

    container.innerHTML = state.tasks.map(task => {
        const priorityClass = `priority-${task.priorite.toLowerCase()}`;
        const isDone = task.est_faite;
        const dueText = task.date_echeance ? `Échéance : ${task.date_echeance}` : "Aucune date limite";

        return `
            <div class="task-item ${isDone ? 'completed' : ''}" id="task-item-${task.id}">
                <div class="task-left">
                    <input 
                        type="checkbox" 
                        class="task-checkbox" 
                        ${isDone ? 'checked' : ''} 
                        onchange="toggleTaskStatus(${task.id}, this.checked)"
                        title="Marquer comme ${isDone ? 'non faite' : 'terminée'}"
                    >
                    <div class="task-content">
                        <span class="task-title">${escapeHtml(task.titre)}</span>
                        <span class="task-due">${dueText}</span>
                    </div>
                </div>

                <div class="task-right">
                    <span class="priority-badge ${priorityClass}">${escapeHtml(task.priorite)}</span>
                    <button class="btn-icon btn-edit" onclick="openEditTaskModal(${task.id})" title="Modifier cette tâche">
                        ✏️
                    </button>
                    <button class="btn-icon" onclick="deleteTask(${task.id})" title="Supprimer cette tâche">
                        🗑️
                    </button>
                </div>
            </div>
        `;
    }).join("");
}

function openEditTaskModal(taskId) {
    const task = state.tasks.find(t => t.id === taskId);
    if (!task) return;

    document.getElementById("edit-task-id").value = task.id;
    document.getElementById("edit-task-titre").value = task.titre;
    document.getElementById("edit-task-date").value = task.date_echeance || "";
    document.getElementById("edit-task-priorite").value = task.priorite;

    openModal("modal-edit-task");
}

async function toggleTaskStatus(taskId, isDone) {
    try {
        const response = await fetch(`/api/tasks/${taskId}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ est_faite: isDone })
        });

        if (!response.ok) throw new Error("Échec de mise à jour");

        const updated = await response.json();
        const idx = state.tasks.findIndex(t => t.id === taskId);
        if (idx !== -1) state.tasks[idx] = updated;

        renderTasks();
        await loadStats();
    } catch (error) {
        showToast("Erreur lors de la mise à jour de la tâche.", "error");
        await loadTasks();
    }
}

async function deleteTask(taskId) {
    try {
        const response = await fetch(`/api/tasks/${taskId}`, {
            method: "DELETE"
        });

        if (!response.ok) throw new Error("Échec de la suppression");

        showToast("Tâche supprimée.", "success");
        await loadDashboardData();
    } catch (error) {
        showToast("Erreur lors de la suppression de la tâche.", "error");
    }
}

/* ==========================================================================
   Statistiques & Synthèse (/api/summary)
   ========================================================================== */
async function loadStats() {
    try {
        const response = await fetch("/api/summary");
        if (!response.ok) throw new Error("Erreur de récupération de la synthèse");

        state.stats = await response.json();
        updateKPIDisplay(state.stats);
    } catch (error) {
        console.warn("Impossible de charger la synthèse:", error);
    }
}

function updateKPIDisplay(stats) {
    const avgElem = document.getElementById("kpi-average");
    const avgDesc = document.getElementById("kpi-average-desc");
    if (stats.general_average !== null && stats.general_average !== undefined) {
        avgElem.innerHTML = `${stats.general_average.toFixed(2)} <span class="kpi-unit">/ 20</span>`;
        if (stats.general_average >= 14) {
            avgDesc.className = "kpi-trend success";
            avgDesc.textContent = "Mention Bien / Très Bien";
        } else if (stats.general_average >= 10) {
            avgDesc.className = "kpi-trend success";
            avgDesc.textContent = "Année validée (≥ 10/20)";
        } else {
            avgDesc.className = "kpi-trend danger";
            avgDesc.textContent = "En dessous de la moyenne";
        }
    } else {
        avgElem.innerHTML = `-- <span class="kpi-unit">/ 20</span>`;
        avgDesc.className = "kpi-trend neutral";
        avgDesc.textContent = "En attente de notes";
    }

    const modulesElem = document.getElementById("kpi-modules-count");
    modulesElem.innerHTML = `${stats.total_modules} <span class="kpi-unit">UE</span>`;

    const tasksElem = document.getElementById("kpi-tasks-pending");
    const tasksUrgentElem = document.getElementById("kpi-tasks-urgent");
    tasksElem.textContent = stats.pending_tasks;
    tasksUrgentElem.textContent = `${stats.high_priority_tasks} prioritaire(s)`;
    tasksUrgentElem.className = stats.high_priority_tasks > 0 ? "kpi-trend warning" : "kpi-trend neutral";

    const successElem = document.getElementById("kpi-success-rate");
    if (stats.success_rate !== null && stats.success_rate !== undefined) {
        successElem.innerHTML = `${stats.success_rate.toFixed(1)} <span class="kpi-unit">%</span>`;
    } else {
        successElem.innerHTML = `-- <span class="kpi-unit">%</span>`;
    }
}

/* ==========================================================================
   Graphiques Statistiques (Chart.js)
   ========================================================================== */
function setupChartToggleListeners() {
    const btnAvg = document.getElementById("btn-chart-averages");
    const btnCoef = document.getElementById("btn-chart-coefficients");

    btnAvg?.addEventListener("click", () => {
        state.chartMode = "averages";
        btnAvg.classList.add("active");
        btnCoef.classList.remove("active");
        renderAcademicChart();
    });

    btnCoef?.addEventListener("click", () => {
        state.chartMode = "coefficients";
        btnCoef.classList.add("active");
        btnAvg.classList.remove("active");
        renderAcademicChart();
    });
}

function renderAcademicChart() {
    const canvas = document.getElementById("academic-chart");
    if (!canvas || typeof Chart === "undefined") return;

    if (academicChartInstance) {
        academicChartInstance.destroy();
    }

    if (!state.modules || state.modules.length === 0) {
        return;
    }

    const ctx = canvas.getContext("2d");

    if (state.chartMode === "averages") {
        // Graphique en barres des moyennes par UE
        const labels = state.modules.map(m => m.code);
        const dataValues = state.modules.map(m => m.average !== null ? m.average : 0);
        const backgroundColors = dataValues.map(v => v >= 10 ? "rgba(16, 185, 129, 0.75)" : "rgba(239, 68, 68, 0.75)");
        const borderColors = dataValues.map(v => v >= 10 ? "#10b981" : "#ef4444");

        academicChartInstance = new Chart(ctx, {
            type: "bar",
            data: {
                labels: labels,
                datasets: [{
                    label: "Moyenne /20",
                    data: dataValues,
                    backgroundColor: backgroundColors,
                    borderColor: borderColors,
                    borderWidth: 1.5,
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (context) => `Moyenne : ${context.parsed.y.toFixed(2)}/20`
                        }
                    }
                },
                scales: {
                    y: {
                        min: 0,
                        max: 20,
                        grid: { color: "rgba(255, 255, 255, 0.08)" },
                        ticks: { color: "#9ca3af", font: { family: "Inter" } }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: "#f9fafb", font: { family: "JetBrains Mono", weight: "600" } }
                    }
                }
            }
        });
    } else {
        // Graphique en anneau (Doughnut) de répartition des coefficients
        const labels = state.modules.map(m => `${m.code} (${m.coefficient})`);
        const dataValues = state.modules.map(m => m.coefficient);
        const palette = [
            "#6366f1", "#10b981", "#06b6d4", "#f59e0b",
            "#ec4899", "#8b5cf6", "#14b8a6", "#3b82f6"
        ];

        academicChartInstance = new Chart(ctx, {
            type: "doughnut",
            data: {
                labels: labels,
                datasets: [{
                    data: dataValues,
                    backgroundColor: palette.slice(0, labels.length),
                    borderColor: "#111827",
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: { color: "#9ca3af", font: { family: "Inter", size: 11 } }
                    }
                }
            }
        });
    }
}

/* ==========================================================================
   Simulateur de Notes & Partiel (Phase 3)
   ========================================================================== */
function setupSimulatorListeners() {
    const modSelect = document.getElementById("sim-module-select");
    const noteInput = document.getElementById("sim-note");
    const coefInput = document.getElementById("sim-coef");

    modSelect?.addEventListener("change", runSimulation);
    noteInput?.addEventListener("input", runSimulation);
    coefInput?.addEventListener("input", runSimulation);
}

function updateSimulatorModuleSelect() {
    const simSelect = document.getElementById("sim-module-select");
    if (!simSelect) return;

    const currentVal = simSelect.value;
    if (state.modules.length === 0) {
        simSelect.innerHTML = `<option value="">Aucun module disponible</option>`;
        return;
    }

    simSelect.innerHTML = `<option value="">Sélectionnez un module...</option>` +
        state.modules.map(m => `<option value="${m.id}">${escapeHtml(m.code)} - ${escapeHtml(m.nom)} (coef ${m.coefficient})</option>`).join("");

    if (currentVal && state.modules.some(m => m.id === parseInt(currentVal, 10))) {
        simSelect.value = currentVal;
    } else if (state.modules.length > 0) {
        simSelect.value = state.modules[0].id;
    }
}

function runSimulation() {
    const modSelect = document.getElementById("sim-module-select");
    const noteInput = document.getElementById("sim-note");
    const coefInput = document.getElementById("sim-coef");

    const modAvgElem = document.getElementById("sim-module-avg");
    const modDeltaElem = document.getElementById("sim-module-delta");
    const modDescElem = document.getElementById("sim-module-desc");

    const genAvgElem = document.getElementById("sim-general-avg");
    const genDeltaElem = document.getElementById("sim-general-delta");
    const genDescElem = document.getElementById("sim-general-desc");

    if (!modSelect || !modSelect.value) {
        modAvgElem.textContent = "-- / 20";
        modDeltaElem.className = "delta-badge neutral";
        modDeltaElem.textContent = "--";
        modDescElem.textContent = "Sélectionnez une matière pour simuler";

        genAvgElem.textContent = "-- / 20";
        genDeltaElem.className = "delta-badge neutral";
        genDeltaElem.textContent = "--";
        return;
    }

    const moduleId = parseInt(modSelect.value, 10);
    const targetModule = state.modules.find(m => m.id === moduleId);
    if (!targetModule) return;

    const simNote = parseFloat(noteInput.value) || 0;
    const simCoef = parseFloat(coefInput.value) || 1.0;

    // Calcul de la nouvelle moyenne pour le module simulé
    let currentPts = 0;
    let currentCoefs = 0;
    if (targetModule.grades && targetModule.grades.length > 0) {
        currentPts = targetModule.grades.reduce((sum, g) => sum + g.note * g.coefficient, 0);
        currentCoefs = targetModule.grades.reduce((sum, g) => sum + g.coefficient, 0);
    }

    const newModuleAvg = (currentPts + simNote * simCoef) / (currentCoefs + simCoef);
    const oldModuleAvg = targetModule.average !== null ? targetModule.average : null;
    const modDelta = oldModuleAvg !== null ? newModuleAvg - oldModuleAvg : null;

    modAvgElem.textContent = `${newModuleAvg.toFixed(2)} / 20`;
    if (modDelta !== null) {
        const sign = modDelta >= 0 ? "+" : "";
        modDeltaElem.textContent = `${sign}${modDelta.toFixed(2)} pt(s)`;
        modDeltaElem.className = `delta-badge ${modDelta >= 0 ? 'positive' : 'negative'}`;
        modDescElem.textContent = `Actuelle: ${oldModuleAvg.toFixed(2)}/20 (avec ${targetModule.grades.length} note(s))`;
    } else {
        modDeltaElem.textContent = "1ère note";
        modDeltaElem.className = "delta-badge neutral";
        modDescElem.textContent = "Première note enregistrée pour cette UE";
    }

    // Calcul de la nouvelle moyenne générale du semestre
    let totalWeightedSum = 0;
    let totalModuleCoefs = 0;

    for (const m of state.modules) {
        if (m.id === targetModule.id) {
            totalWeightedSum += newModuleAvg * m.coefficient;
            totalModuleCoefs += m.coefficient;
        } else if (m.average !== null) {
            totalWeightedSum += m.average * m.coefficient;
            totalModuleCoefs += m.coefficient;
        }
    }

    const newGeneralAvg = totalModuleCoefs > 0 ? (totalWeightedSum / totalModuleCoefs) : newModuleAvg;
    const oldGeneralAvg = state.stats && state.stats.general_average !== null ? state.stats.general_average : null;
    const genDelta = oldGeneralAvg !== null ? newGeneralAvg - oldGeneralAvg : null;

    genAvgElem.textContent = `${newGeneralAvg.toFixed(2)} / 20`;
    if (genDelta !== null) {
        const sign = genDelta >= 0 ? "+" : "";
        genDeltaElem.textContent = `${sign}${genDelta.toFixed(2)} pt(s)`;
        genDeltaElem.className = `delta-badge ${genDelta >= 0 ? 'positive' : 'negative'}`;
        genDescElem.textContent = `Actuelle: ${oldGeneralAvg.toFixed(2)}/20`;
    } else {
        genDeltaElem.textContent = "Nouveau";
        genDeltaElem.className = "delta-badge neutral";
        genDescElem.textContent = "Simulation initiale";
    }
}

/* ==========================================================================
   Gestion des Modales (Ouverture / Fermeture / Clavier)
   ========================================================================== */
function setupModalListeners() {
    document.getElementById("btn-add-module")?.addEventListener("click", () => openModal("modal-module"));
    document.getElementById("btn-add-task")?.addEventListener("click", () => openModal("modal-task"));
    document.getElementById("btn-import-ics")?.addEventListener("click", () => openModal("modal-import-ics"));
    document.getElementById("btn-clear-tasks")?.addEventListener("click", async () => {
        if (!confirm("Voulez-vous réinitialiser le planning et supprimer toutes les tâches ? (Les matières et les notes seront conservées)")) {
            return;
        }

        try {
            const response = await fetch("/api/tasks", { method: "DELETE" });
            if (!response.ok) throw new Error("Erreur de suppression");
            const data = await response.json();
            showToast(data.message || "Planning réinitialisé.", "success");
            await loadDashboardData();
        } catch (error) {
            showToast("Impossible de réinitialiser le planning.", "error");
        }
    });
    document.getElementById("btn-reset-planning")?.addEventListener("click", async () => {
        if (!confirm("Réinitialiser le planning importé ?\nSupprime : toutes les séances, les tâches importées (📝) et les modules sans note.\nConservé : les modules ayant des notes et vos tâches créées à la main.")) {
            return;
        }
        try {
            const response = await fetch("/api/planning", { method: "DELETE" });
            if (!response.ok) throw new Error("Erreur de réinitialisation");
            const data = await response.json();
            showToast(data.message || "Planning réinitialisé.", "success");
            await loadDashboardData();
            await loadWeeklySchedule(true);
        } catch (error) {
            showToast("Impossible de réinitialiser le planning.", "error");
        }
    });
    document.getElementById("btn-open-grade-modal")?.addEventListener("click", () => {
        if (state.modules.length === 0) {
            showToast("Veuillez créer un module avant d'ajouter une note.", "error");
            openModal("modal-module");
            return;
        }
        openModal("modal-grade");
    });

    document.querySelectorAll("[data-close-modal]").forEach(button => {
        button.addEventListener("click", () => {
            const modalId = button.getAttribute("data-close-modal");
            closeModal(modalId);
        });
    });

    document.querySelectorAll(".modal-backdrop").forEach(backdrop => {
        backdrop.addEventListener("click", (e) => {
            if (e.target === backdrop) {
                closeModal(backdrop.id);
            }
        });
    });

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            document.querySelectorAll(".modal-backdrop.active").forEach(modal => {
                closeModal(modal.id);
            });
        }
    });
}

function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;

    modal.classList.add("active");
    modal.setAttribute("aria-hidden", "false");

    const firstInput = modal.querySelector("input, select");
    if (firstInput) {
        setTimeout(() => firstInput.focus(), 50);
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;

    modal.classList.remove("active");
    modal.setAttribute("aria-hidden", "true");
}

/* ==========================================================================
   Soumission des Formulaires (Fetch API)
   ========================================================================== */
function setupFormListeners() {
    // 1. Formulaire Nouveau Module
    const formModule = document.getElementById("form-add-module");
    if (formModule) {
        formModule.addEventListener("submit", async (e) => {
            e.preventDefault();
            const nom = document.getElementById("module-nom").value.trim();
            const code = document.getElementById("module-code").value.trim().toUpperCase();
            const coef = parseFloat(document.getElementById("module-coef").value);

            try {
                const response = await fetch("/api/modules", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ nom, code, coefficient: coef })
                });

                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.detail || "Erreur lors de la création du module");
                }

                formModule.reset();
                closeModal("modal-module");
                showToast(`Module ${code} ajouté avec succès !`, "success");
                await loadDashboardData();
            } catch (error) {
                showToast(error.message, "error");
            }
        });
    }

    // 2. Formulaire Nouvelle Note
    const formGrade = document.getElementById("form-add-grade");
    if (formGrade) {
        formGrade.addEventListener("submit", async (e) => {
            e.preventDefault();
            const moduleId = parseInt(document.getElementById("grade-module-id").value, 10);
            const intitule = document.getElementById("grade-intitule").value.trim();
            const note = parseFloat(document.getElementById("grade-note").value);
            const coef = parseFloat(document.getElementById("grade-coef").value);
            const dateVal = document.getElementById("grade-date").value;

            if (!moduleId) {
                showToast("Veuillez sélectionner un module.", "error");
                return;
            }

            try {
                const response = await fetch("/api/grades", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        module_id: moduleId,
                        intitule,
                        note,
                        coefficient: coef,
                        date: dateVal || null
                    })
                });

                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.detail || "Erreur lors de l'enregistrement de la note");
                }

                formGrade.reset();
                closeModal("modal-grade");
                showToast(`Note de ${note}/20 enregistrée !`, "success");
                await loadDashboardData();
            } catch (error) {
                showToast(error.message, "error");
            }
        });
    }

    // 3. Formulaire Nouvelle Tâche
    const formTask = document.getElementById("form-add-task");
    if (formTask) {
        formTask.addEventListener("submit", async (e) => {
            e.preventDefault();
            const titre = document.getElementById("task-titre").value.trim();
            const dateVal = document.getElementById("task-date").value;
            const priorite = document.getElementById("task-priorite").value;

            try {
                const response = await fetch("/api/tasks", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        titre,
                        date_echeance: dateVal || null,
                        priorite,
                        est_faite: false
                    })
                });

                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.detail || "Erreur de création de la tâche");
                }

                formTask.reset();
                closeModal("modal-task");
                showToast("Tâche ajoutée au planning !", "success");
                await loadDashboardData();
            } catch (error) {
                showToast(error.message, "error");
            }
        });
    }

    // 4. Formulaire Modification de Tâche (Phase 3)
    const formEditTask = document.getElementById("form-edit-task");
    if (formEditTask) {
        formEditTask.addEventListener("submit", async (e) => {
            e.preventDefault();
            const taskId = parseInt(document.getElementById("edit-task-id").value, 10);
            const titre = document.getElementById("edit-task-titre").value.trim();
            const dateVal = document.getElementById("edit-task-date").value;
            const priorite = document.getElementById("edit-task-priorite").value;

            try {
                const response = await fetch(`/api/tasks/${taskId}`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        titre,
                        date_echeance: dateVal || null,
                        priorite
                    })
                });

                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.detail || "Erreur de modification de la tâche");
                }

                closeModal("modal-edit-task");
                showToast("Tâche modifiée avec succès !", "success");
                await loadDashboardData();
            } catch (error) {
                showToast(error.message, "error");
            }
        });
    }

    // 5. Formulaire Importation ICS (Upload de fichier et URL via FormData)
    const formImportIcs = document.getElementById("form-import-ics");
    if (formImportIcs) {
        formImportIcs.addEventListener("submit", async (e) => {
            e.preventDefault();
            const urlInput   = document.getElementById("ics-url-input");
            const fileInput  = document.getElementById("ics-file-input");
            const groupInput = document.getElementById("ics-group-input");
            const submitBtn  = document.getElementById("btn-submit-import-ics");

            const icsUrl    = urlInput   ? urlInput.value.trim()  : "";
            const groupVal  = groupInput ? groupInput.value.trim() : "";
            const file      = fileInput && fileInput.files ? fileInput.files[0] : null;

            if (!file && !icsUrl) {
                showToast("Veuillez sélectionner un fichier .ics ou renseigner une URL.", "error");
                return;
            }

            const originalBtnText = submitBtn.textContent;
            submitBtn.disabled = true;
            submitBtn.textContent = "Importation en cours… ⏳";

            try {
                const formData = new FormData();
                if (file) {
                    formData.append("file", file);
                } else if (icsUrl) {
                    formData.append("ics_url", icsUrl);
                }
                // Filtre groupe : toujours inclus (vide = pas de filtre)
                if (groupVal) {
                    formData.append("group_filter", groupVal);
                }

                const response = await fetch("/api/import-ics", {
                    method: "POST",
                    body: formData
                });

                const result = await response.json();

                if (!response.ok) {
                    throw new Error(result.detail || "Erreur lors de l'importation iCalendar");
                }

                // Succès
                showToast(result.message || "Calendrier importé avec succès !", "success");
                formImportIcs.reset();
                closeModal("modal-import-ics");
                await loadDashboardData();
                // Afficher la section emploi du temps si des cours ont été importés
                currentWeekOffset = 0;
                await loadWeeklySchedule(true);
            } catch (error) {
                console.error("Erreur import ICS:", error);
                showToast(error.message || "Échec de l'importation du calendrier.", "error");
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = originalBtnText;
            }
        });
    }
}

/* ==========================================================================
   Toasts & Utilitaires
   ========================================================================== */
function showToast(message, type = "success") {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    const icon = type === "success" ? "✅" : "⚠️";
    toast.innerHTML = `<span>${icon}</span> <span>${escapeHtml(message)}</span>`;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateX(20px)";
        toast.style.transition = "all 0.3s ease-out";
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

function escapeHtml(text) {
    if (!text) return "";
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

/* ==========================================================================
   Emploi du Temps Hebdomadaire (Cours ICS)
   ========================================================================== */

// État de la semaine affichée
let currentWeekOffset = 0;  // 0 = semaine courante, -1 = précédente, +1 = suivante
let allCours = [];          // toutes les séances (chargées une fois par rafraîchissement)

function localISO(d) {
    const p = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

/**
 * Retourne un objet { monday, sunday, label, isoWeek } pour un offset de semaine.
 */
function getWeekDates(offset = 0) {
    const now = new Date();
    const dayOfWeek = now.getDay(); // 0=dim, 1=lun…
    const diffToMonday = (dayOfWeek === 0) ? -6 : 1 - dayOfWeek;
    const monday = new Date(now);
    monday.setDate(now.getDate() + diffToMonday + offset * 7);

    const sunday = new Date(monday);
    sunday.setDate(monday.getDate() + 6);

    const toISO = localISO;

    const weekNum = getISOWeekNumber(monday);
    const year = monday.getFullYear();
    const label = `Semaine ${weekNum} • ${monday.toLocaleDateString("fr-FR", { day: "numeric", month: "short" })} – ${sunday.toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" })}`;

    return {
        monday: toISO(monday),
        sunday: toISO(sunday),
        label,
        isoWeek: `${year}-W${String(weekNum).padStart(2, "0")}`
    };
}

function getISOWeekNumber(d) {
    const date = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
    date.setUTCDate(date.getUTCDate() + 4 - (date.getUTCDay() || 7));
    const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
    return Math.ceil((((date - yearStart) / 86400000) + 1) / 7);
}

async function loadWeeklySchedule(refetch = true) {
    const section = document.getElementById("section-planning-hebdo");
    const container = document.getElementById("weekly-schedule-container");
    const weekLabel = document.getElementById("week-label");
    if (!section || !container) return;

    // Navigation : branchée une seule fois, indépendamment du contenu de la semaine
    const btnPrev  = document.getElementById("btn-week-prev");
    const btnNext  = document.getElementById("btn-week-next");
    const btnToday = document.getElementById("btn-week-today");
    if (btnPrev && !btnPrev.dataset.bound) {
        btnPrev.dataset.bound = "1";
        btnPrev.addEventListener("click", () => { currentWeekOffset--; loadWeeklySchedule(false); });
        btnNext.addEventListener("click", () => { currentWeekOffset++; loadWeeklySchedule(false); });
        btnToday.addEventListener("click", () => { currentWeekOffset = 0; loadWeeklySchedule(false); });
    }

    try {
        if (refetch) {
            const response = await fetch("/api/cours");
            if (!response.ok) throw new Error("Erreur chargement cours");
            allCours = await response.json();
        }

        if (allCours.length === 0) {
            section.style.display = "none";   // rien d'importé : section masquée
            return;
        }
        section.style.display = "";

        const week = getWeekDates(currentWeekOffset);
        if (weekLabel) weekLabel.textContent = week.label;
        const inWeek = allCours.filter(c => c.date_cours >= week.monday && c.date_cours <= week.sunday);
        renderWeeklySchedule(inWeek, week);
    } catch (err) {
        console.warn("Impossible de charger le planning hebdomadaire:", err);
    }
}

function renderWeeklySchedule(cours, week) {
    const container = document.getElementById("weekly-schedule-container");
    const DAYS_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"];
    const TYPE_COLORS = {
        "CM":    { bg: "#1e3a5f", border: "#3b82f6", badge: "#3b82f6", label: "CM" },
        "TD":    { bg: "#1a3d2e", border: "#10b981", badge: "#10b981", label: "TD" },
        "TP":    { bg: "#3d2c1a", border: "#f59e0b", badge: "#f59e0b", label: "TP" },
        "COURS": { bg: "#1a1f3d", border: "#8b5cf6", badge: "#8b5cf6", label: "Cours" },
        "EXAM":  { bg: "#3f1d24", border: "#ef4444", badge: "#ef4444", label: "ÉVAL" },
        "TUTORAT": { bg: "#2a2a35", border: "#94a3b8", badge: "#64748b", label: "Tutorat" },
    };

    // Regrouper par jour
    const byDay = {};
    for (let i = 0; i < 7; i++) {
        const d = new Date(week.monday + "T12:00:00");
        d.setDate(d.getDate() + i);
        byDay[localISO(d)] = [];
    }
    for (const c of cours) {
        if (byDay[c.date_cours] !== undefined) {
            byDay[c.date_cours].push(c);
        }
    }

    let html = '<div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap:0.75rem;">';

    let dayIndex = 0;
    for (const [dateStr, dayEvents] of Object.entries(byDay)) {
        const dayName = DAYS_FR[dayIndex];
        const dateObj = new Date(dateStr + "T12:00:00");
        const dateLabel = dateObj.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
        const isToday = dateStr === localISO(new Date());

        html += `
        <div style="
            background: ${isToday ? 'rgba(99,102,241,0.12)' : 'rgba(255,255,255,0.03)'};
            border: 1px solid ${isToday ? '#6366f1' : 'rgba(255,255,255,0.07)'};
            border-radius: 8px;
            padding: 0.6rem;
            min-height: 80px;
        ">
            <div style="font-weight:600; font-size:0.75rem; color:${isToday ? '#818cf8' : '#9ca3af'}; margin-bottom:0.4rem; text-transform:uppercase; letter-spacing:0.05em;">
                ${dayName} <span style="font-weight:400;">${dateLabel}</span>
                ${isToday ? '<span style="color:#6366f1;margin-left:4px;">•</span>' : ''}
            </div>
        `;

        if (dayEvents.length === 0) {
            html += `<div style="color:#4b5563; font-size:0.75rem; font-style:italic; text-align:center; padding-top:0.4rem;">—</div>`;
        } else {
            for (const ev of dayEvents.sort((a, b) => (a.heure_debut || "").localeCompare(b.heure_debut || ""))) {
                const style = TYPE_COLORS[ev.type_cours] || TYPE_COLORS["COURS"];
                const timeStr = ev.heure_debut ? `${ev.heure_debut}${ev.heure_fin ? '–' + ev.heure_fin : ''}` : '';
                const salle = ev.salle ? `🏛️ ${escapeHtml(ev.salle.split(',')[0])}` : '';

                html += `
                <div style="
                    background: ${style.bg};
                    border-left: 3px solid ${style.border};
                    border-radius: 4px;
                    padding: 0.35rem 0.5rem;
                    margin-bottom: 0.4rem;
                    font-size: 0.78rem;
                ">
                    <div style="display:flex; align-items:center; gap:4px; margin-bottom:2px;">
                        <span style="
                            background: ${style.badge};
                            color: #fff;
                            font-size: 0.65rem;
                            font-weight: 700;
                            padding: 1px 5px;
                            border-radius: 3px;
                            font-family: 'JetBrains Mono', monospace;
                        ">${style.label}</span>
                        <span style="color:#e5e7eb; font-weight:600; font-size:0.73rem;">${escapeHtml(ev.type_cours === "TUTORAT" ? "" : ev.module_code)}</span>
                    </div>
                    <div style="color:#d1d5db; font-size:0.72rem; line-height:1.3;">${escapeHtml(ev.module_nom)}</div>
                    ${timeStr ? `<div style="color:#9ca3af; font-size:0.68rem; margin-top:2px;">⏰ ${timeStr}</div>` : ''}
                    ${salle ? `<div style="color:#9ca3af; font-size:0.68rem;">${salle}</div>` : ''}
                </div>`;
            }
        }

        html += `</div>`;
        dayIndex++;
    }

    html += '</div>';
    container.innerHTML = html;
}

// Tenter de charger le planning hebdo au démarrage (si des cours existent déjà)
async function tryLoadWeeklySchedule() {
    try { await loadWeeklySchedule(true); } catch (_) { /* silencieux */ }
}
