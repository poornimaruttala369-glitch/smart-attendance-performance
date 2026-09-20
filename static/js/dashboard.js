/**
 * KIET Smart Attendance and Performance Analyser
 * JavaScript for Dynamic Charts, Table Filters, Modal Dialogs, and Interactive Calculations
 */

document.addEventListener('DOMContentLoaded', () => {
    // Mobile navigation toggle
    const mobileBtn = document.getElementById('mobileMenuBtn');
    const navLinks = document.getElementById('navLinks');
    if (mobileBtn && navLinks) {
        mobileBtn.addEventListener('click', () => {
            navLinks.classList.toggle('show');
        });
    }

    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });

    // Student Management Table Filter
    initStudentFilter();

    // Attendance Inline Calculator
    initAttendanceCalculator();

    // Marks Inline Calculator
    initMarksCalculator();

    // Branch Comparison Charts initialization
    if (typeof window.BRANCH_DATA !== 'undefined') {
        initBranchCharts(window.BRANCH_DATA);
    }

    // Student Dashboard Charts initialization
    if (typeof window.STUDENT_DATA !== 'undefined') {
        initStudentCharts(window.STUDENT_DATA);
    }
});

// Modal helpers
function openModal(id) {
    const modal = document.getElementById(id);
    if (modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

function closeModal(id) {
    const modal = document.getElementById(id);
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
}

// Close modal when clicking outside dialog
window.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal')) {
        e.target.classList.remove('active');
        document.body.style.overflow = '';
    }
});

/**
 * Filter students table dynamically by search query, branch, semester, and status
 */
function initStudentFilter() {
    const searchInput = document.getElementById('studentSearch');
    const branchFilter = document.getElementById('filterBranch');
    const semFilter = document.getElementById('filterSemester');
    const statusFilter = document.getElementById('filterStatus');
    const table = document.getElementById('studentsTable');

    if (!table) return;

    const rows = table.querySelectorAll('tbody tr');

    function applyFilter() {
        const query = searchInput ? searchInput.value.toLowerCase().trim() : '';
        const branch = branchFilter ? branchFilter.value : '';
        const sem = semFilter ? semFilter.value : '';
        const status = statusFilter ? statusFilter.value : '';

        let visibleCount = 0;

        rows.forEach(row => {
            const name = row.getAttribute('data-name') ? row.getAttribute('data-name').toLowerCase() : '';
            const roll = row.getAttribute('data-roll') ? row.getAttribute('data-roll').toLowerCase() : '';
            const rowBranch = row.getAttribute('data-branch') || '';
            const rowSem = row.getAttribute('data-sem') || '';
            const rowStatus = row.getAttribute('data-status') || '';

            const matchesSearch = !query || name.includes(query) || roll.includes(query);
            const matchesBranch = !branch || rowBranch === branch;
            const matchesSem = !sem || rowSem === sem;
            const matchesStatus = !status || rowStatus === status;

            if (matchesSearch && matchesBranch && matchesSem && matchesStatus) {
                row.style.display = '';
                visibleCount++;
            } else {
                row.style.display = 'none';
            }
        });

        const countBadge = document.getElementById('filteredCount');
        if (countBadge) {
            countBadge.innerText = `${visibleCount} students shown`;
        }
    }

    if (searchInput) searchInput.addEventListener('input', applyFilter);
    if (branchFilter) branchFilter.addEventListener('change', applyFilter);
    if (semFilter) semFilter.addEventListener('change', applyFilter);
    if (statusFilter) statusFilter.addEventListener('change', applyFilter);
}

/**
 * Real-time Attendance percentage & color recalculation on input change
 */
function initAttendanceCalculator() {
    const rows = document.querySelectorAll('.attendance-calc-row');
    rows.forEach(row => {
        const totalInput = row.querySelector('.total-classes-input');
        const attendedInput = row.querySelector('.attended-classes-input');
        const pctDisplay = row.querySelector('.calc-pct-display');
        const barFill = row.querySelector('.calc-bar-fill');

        function updateAttendance() {
            const total = parseFloat(totalInput.value) || 0;
            const attended = parseFloat(attendedInput.value) || 0;

            if (attended > total && total > 0) {
                attendedInput.value = total;
            }

            let pct = 0;
            if (total > 0) {
                pct = Math.round((Math.min(attended, total) / total) * 100 * 10) / 10;
            }

            if (pctDisplay) {
                pctDisplay.innerText = pct.toFixed(1) + '%';
            }

            if (barFill) {
                barFill.style.width = pct + '%';
                barFill.className = 'progress-fill ' + getAttendanceColorClass(pct);
            }
        }

        if (totalInput) totalInput.addEventListener('input', updateAttendance);
        if (attendedInput) attendedInput.addEventListener('input', updateAttendance);
    });
}

/**
 * Real-time Marks percentage recalculation on input change
 */
function initMarksCalculator() {
    const rows = document.querySelectorAll('.marks-calc-row');
    rows.forEach(row => {
        const obtainedInput = row.querySelector('.marks-obtained-input');
        const maxInput = row.querySelector('.marks-max-input');
        const pctDisplay = row.querySelector('.marks-pct-display');

        function updateMarks() {
            const obtained = parseFloat(obtainedInput.value) || 0;
            const maxMarks = parseFloat(maxInput.value) || 100;

            let pct = 0;
            if (maxMarks > 0) {
                pct = Math.round((obtained / maxMarks) * 100 * 10) / 10;
            }

            if (pctDisplay) {
                pctDisplay.innerText = pct.toFixed(1) + '%';
            }
        }

        if (obtainedInput) obtainedInput.addEventListener('input', updateMarks);
        if (maxInput) maxInput.addEventListener('input', updateMarks);
    });
}

function getAttendanceColorClass(pct) {
    if (pct >= 75.0) return 'progress-green';
    if (pct >= 70.0) return 'progress-yellow';
    return 'progress-red';
}

/**
 * Initialize all 6 Chart.js graphs for the Branch Comparison Page
 */
function initBranchCharts(data) {
    if (typeof Chart === 'undefined') {
        console.warn('Chart.js library is not loaded.');
        return;
    }

    const branchColors = {
        'AI': '#2563eb',
        'AIDS': '#0284c7',
        'AIML': '#7c3aed',
        'DS': '#059669',
        'CYBER': '#dc2626'
    };

    const labels = data.branches; // ['AI', 'AIDS', 'AIML', 'DS', 'CYBER']
    const colors = labels.map(b => branchColors[b] || '#3b82f6');

    // 1. Total Students in Each Branch (Bar Chart)
    const ctxStudents = document.getElementById('chartBranchStudents');
    if (ctxStudents) {
        new Chart(ctxStudents, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Total Students',
                    data: data.studentCounts,
                    backgroundColor: colors,
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, ticks: { precision: 0 } }
                }
            }
        });
    }

    // 2. Average Attendance Percentage (Bar Chart)
    const ctxAttendance = document.getElementById('chartBranchAttendance');
    if (ctxAttendance) {
        new Chart(ctxAttendance, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Avg Attendance %',
                    data: data.avgAttendance,
                    backgroundColor: colors,
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    tooltip: {
                        callbacks: { label: ctx => `Avg Attendance: ${ctx.raw}%` }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: { callback: v => v + '%' }
                    }
                }
            }
        });
    }

    // 3. Average Marks (Bar Chart)
    const ctxMarks = document.getElementById('chartBranchMarks');
    if (ctxMarks) {
        new Chart(ctxMarks, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Avg Marks %',
                    data: data.avgMarks,
                    backgroundColor: colors,
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    tooltip: {
                        callbacks: { label: ctx => `Avg Marks: ${ctx.raw}%` }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: { callback: v => v + '%' }
                    }
                }
            }
        });
    }

    // 4. Student Status Distribution (Doughnut Chart)
    const ctxStatus = document.getElementById('chartStatusDistribution');
    if (ctxStatus) {
        new Chart(ctxStatus, {
            type: 'doughnut',
            data: {
                labels: ['On Track', 'Monitor', 'Needs Attention'],
                datasets: [{
                    data: [
                        data.statusDistribution.onTrack || 0,
                        data.statusDistribution.monitor || 0,
                        data.statusDistribution.needsAttention || 0
                    ],
                    backgroundColor: ['#16a34a', '#f59e0b', '#dc2626'],
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom' }
                }
            }
        });
    }

    // 5. Relationship Between Attendance and Marks (Scatter Chart)
    const ctxScatter = document.getElementById('chartAttendanceVsMarks');
    if (ctxScatter) {
        new Chart(ctxScatter, {
            type: 'scatter',
            data: {
                datasets: [{
                    label: 'Students (Attendance vs Marks)',
                    data: data.studentPoints || [], // array of {x: att_pct, y: marks_pct}
                    backgroundColor: 'rgba(37, 99, 235, 0.7)',
                    borderColor: '#1d4ed8',
                    pointRadius: 6,
                    pointHoverRadius: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        title: { display: true, text: 'Attendance Percentage (%)' },
                        min: 30,
                        max: 100
                    },
                    y: {
                        title: { display: true, text: 'Average Marks Percentage (%)' },
                        min: 20,
                        max: 100
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: ctx => {
                                const pt = ctx.raw;
                                const roll = pt.roll ? ` [${pt.roll}]` : '';
                                return `${pt.name || 'Student'}${roll}: Att ${pt.x}%, Marks ${pt.y}%`;
                            }
                        }
                    }
                }
            }
        });
    }

    // 6. Subject-wise Average Marks (Bar Chart)
    const ctxSubjects = document.getElementById('chartSubjectMarks');
    if (ctxSubjects && data.subjectMarks) {
        new Chart(ctxSubjects, {
            type: 'bar',
            data: {
                labels: data.subjectMarks.labels,
                datasets: [{
                    label: 'Subject Avg Marks %',
                    data: data.subjectMarks.values,
                    backgroundColor: '#3b82f6',
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y', // Horizontal bars for clean reading of long subject names
                scales: {
                    x: {
                        beginAtZero: true,
                        max: 100,
                        ticks: { callback: v => v + '%' }
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: { label: ctx => `Avg Marks: ${ctx.raw}%` }
                    }
                }
            }
        });
    }
}

/**
 * Initialize Charts for Student Dashboard (Student's own attendance & marks)
 */
function initStudentCharts(studentData) {
    if (typeof Chart === 'undefined') return;

    // 1. Subject-wise Attendance Bar Chart with 75% threshold line
    const ctxAtt = document.getElementById('studentAttendanceChart');
    if (ctxAtt && studentData.attendance) {
        new Chart(ctxAtt, {
            type: 'bar',
            data: {
                labels: studentData.attendance.labels,
                datasets: [
                    {
                        label: 'My Attendance %',
                        data: studentData.attendance.values,
                        backgroundColor: studentData.attendance.values.map(v => 
                            v >= 75 ? '#16a34a' : (v >= 70 ? '#f59e0b' : '#dc2626')
                        ),
                        borderRadius: 5
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: { callback: v => v + '%' }
                    },
                    x: {
                        ticks: {
                            maxRotation: 45,
                            minRotation: 20
                        }
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: ctx => `Attendance: ${ctx.raw}%`
                        }
                    }
                }
            }
        });
    }

    // 2. Subject-wise Marks Bar Chart
    const ctxMarks = document.getElementById('studentMarksChart');
    if (ctxMarks && studentData.marks) {
        new Chart(ctxMarks, {
            type: 'bar',
            data: {
                labels: studentData.marks.labels,
                datasets: [
                    {
                        label: 'My Marks %',
                        data: studentData.marks.values,
                        backgroundColor: studentData.marks.values.map(v => 
                            v >= 50 ? '#2563eb' : (v >= 40 ? '#f59e0b' : '#dc2626')
                        ),
                        borderRadius: 5
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: { callback: v => v + '%' }
                    },
                    x: {
                        ticks: {
                            maxRotation: 45,
                            minRotation: 20
                        }
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: ctx => `Marks: ${ctx.raw}%`
                        }
                    }
                }
            }
        });
    }
}
