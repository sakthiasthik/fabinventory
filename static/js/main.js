// FabInventory Main JavaScript

// Auto-hide alerts after 5 seconds
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(function(alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
});

// Confirm dangerous actions
function confirmAction(message) {
    return confirm(message || 'Are you sure?');
}

// Format numbers with commas
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// Highlight search results
function highlightSearch(text, searchTerm) {
    if (!searchTerm) return text;
    const regex = new RegExp(`(${searchTerm})`, 'gi');
    return text.replace(regex, '<mark>$1</mark>');
}

// Table search functionality
function initTableSearch(tableId, searchInputId) {
    const searchInput = document.getElementById(searchInputId);
    if (!searchInput) return;
    
    searchInput.addEventListener('keyup', function() {
        const searchTerm = this.value.toLowerCase();
        const table = document.getElementById(tableId);
        const rows = table.getElementsByTagName('tr');
        
        for (let i = 1; i < rows.length; i++) {
            let found = false;
            const cells = rows[i].getElementsByTagName('td');
            
            for (let j = 0; j < cells.length; j++) {
                const cellText = cells[j].textContent.toLowerCase();
                if (cellText.includes(searchTerm)) {
                    found = true;
                    break;
                }
            }
            
            rows[i].style.display = found ? '' : 'none';
        }
    });
}

// Export table to CSV
function exportTableToCSV(tableId, filename) {
    const table = document.getElementById(tableId);
    const rows = table.querySelectorAll('tr');
    const csv = [];
    
    for (let i = 0; i < rows.length; i++) {
        const row = [], cols = rows[i].querySelectorAll('td, th');
        
        for (let j = 0; j < cols.length; j++) {
            let data = cols[j].innerText.replace(/(\r\n|\n|\r)/gm, ' ');
            data = data.replace(/(\s+)/gm, ' ');
            row.push('"' + data + '"');
        }
        
        csv.push(row.join(','));
    }
    
    const csvFile = new Blob([csv.join('\n')], {type: 'text/csv'});
    const downloadLink = document.createElement('a');
    downloadLink.download = filename;
    downloadLink.href = window.URL.createObjectURL(csvFile);
    downloadLink.style.display = 'none';
    document.body.appendChild(downloadLink);
    downloadLink.click();
    document.body.removeChild(downloadLink);
}

// Initialize tooltips
var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
});

/* ============================================================
   Fixed-height table blocks with in-block pagination
   ============================================================
   Markup: <div class="fi-table-scroll" data-page-size="25">
               <table>…</table>
           </div>
           (a .fi-pager control bar is created right after the block)
   Search/filter code should set row.style.display as usual and then
   call refreshFiPager(container) so the pager recomputes its pages.
   Pager hiding uses the .fi-page-hidden class (never style.display),
   so it can never fight with search filtering.
============================================================ */

function initPagedTable(container, pageSize) {
    if (!container || container.dataset.fiPagerInit) return;
    var table = container.querySelector('table');
    if (!table) return;
    var tbody = table.querySelector('tbody');
    if (!tbody) return;
    container.dataset.fiPagerInit = '1';

    var state = { page: 1, pageSize: pageSize || 25 };
    container._fiPagerState = state;

    var pager = (container.nextElementSibling &&
                 container.nextElementSibling.classList.contains('fi-pager'))
        ? container.nextElementSibling : null;
    if (!pager) {
        pager = document.createElement('div');
        pager.className = 'fi-pager';
        container.insertAdjacentElement('afterend', pager);
    }

    pager.innerHTML =
        '<span class="fi-pager-info"></span>' +
        '<div class="fi-pager-controls">' +
        '  <select class="form-select form-select-sm fi-pager-size">' +
        '    <option value="10">10 / page</option>' +
        '    <option value="25">25 / page</option>' +
        '    <option value="50">50 / page</option>' +
        '    <option value="100">100 / page</option>' +
        '    <option value="0">All rows</option>' +
        '  </select>' +
        '  <button type="button" class="btn btn-sm btn-outline-secondary fi-pager-prev">Prev</button>' +
        '  <span class="fi-pager-page"></span>' +
        '  <button type="button" class="btn btn-sm btn-outline-secondary fi-pager-next">Next</button>' +
        '</div>';

    pager.querySelector('.fi-pager-size').value = String(state.pageSize);
    pager.querySelector('.fi-pager-size').addEventListener('change', function (e) {
        state.pageSize = parseInt(e.target.value, 10) || 0;
        state.page = 1;
        renderPager();
    });
    pager.querySelector('.fi-pager-prev').addEventListener('click', function () {
        state.page = Math.max(1, state.page - 1);
        renderPager();
    });
    pager.querySelector('.fi-pager-next').addEventListener('click', function () {
        state.page = Math.min(totalPages(), state.page + 1);
        renderPager();
    });

    function rows() {
        return Array.prototype.slice.call(tbody.querySelectorAll('tr'))
            .filter(function (r) { return r.style.display !== 'none'; });
    }
    function totalPages() {
        return state.pageSize > 0 ? Math.max(1, Math.ceil(rows().length / state.pageSize)) : 1;
    }
    function sizeBlock() {
        // Fit the block to the rows on the current page. Changing the
        // page size (10 / 25 / 50 / 100) therefore grows or shrinks the
        // block and moves the footer down/up with it, instead of
        // showing a tiny fixed window of ~5 rows.
        var onPage = rows().filter(function (r) {
            return !r.classList.contains('fi-page-hidden');
        });
        if (!onPage.length) {
            container.style.maxHeight = '';
            return;
        }
        var headerH = table.tHead ? table.tHead.getBoundingClientRect().height : 0;
        var bodyH = 0;
        onPage.forEach(function (r) {
            bodyH += r.getBoundingClientRect().height;
        });
        if (!bodyH) {
            // Table sits in a hidden Bootstrap tab pane: measure nothing,
            // so use a sensible estimate and recalculate on shown.bs.tab.
            headerH = headerH || 42;
            bodyH = onPage.length * 44;
        }
        container.style.maxHeight = Math.ceil(headerH + bodyH + 2) + 'px';
    }
    function renderPager() {
        var all = rows();
        var total = all.length;
        var pages = totalPages();
        if (state.page > pages) state.page = pages;

        all.forEach(function (row, i) {
            var onPage;
            if (state.pageSize === 0) {
                onPage = true;
            } else {
                onPage = i >= (state.page - 1) * state.pageSize && i < state.page * state.pageSize;
            }
            row.classList.toggle('fi-page-hidden', !onPage);
        });

        var from = total === 0 ? 0 : (state.page - 1) * state.pageSize + 1;
        var to = state.pageSize === 0 ? total : Math.min(state.page * state.pageSize, total);
        pager.querySelector('.fi-pager-info').textContent =
            total ? ('Showing ' + from + '–' + to + ' of ' + total) : 'No rows';
        pager.querySelector('.fi-pager-page').textContent =
            total ? ('Page ' + state.page + ' / ' + pages) : '';
        pager.querySelector('.fi-pager-prev').disabled = state.page <= 1;
        pager.querySelector('.fi-pager-next').disabled = state.page >= pages;

        // Keep the bar visible for short lists too: it holds the
        // "rows per page" selector, so hiding it would trap the user
        // at the current page size. The single placeholder row of an
        // empty section gets no pager.
        var emptyPlaceholder = total === 1 && tbody.querySelector('td[colspan]');
        pager.style.display = (total > 0 && !emptyPlaceholder) ? '' : 'none';
        sizeBlock();
    }
    container._fiPagerRender = renderPager;
    container._fiPagerSize = sizeBlock;
    renderPager();
}

function refreshFiPager(container) {
    if (container && container._fiPagerRender) {
        container._fiPagerState.page = 1;
        container._fiPagerRender();
    }
}

function refreshFiPagerSizes() {
    document.querySelectorAll('.fi-table-scroll').forEach(function (el) {
        if (el._fiPagerSize) el._fiPagerSize();
    });
}

document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.fi-table-scroll').forEach(function (el) {
        initPagedTable(el, parseInt(el.dataset.pageSize || '25', 10));
    });
    // Row heights change with viewport width (text wraps) and when a
    // hidden tab becomes visible (it measured as zero until then).
    window.addEventListener('resize', refreshFiPagerSizes);
    document.addEventListener('shown.bs.tab', refreshFiPagerSizes);
});

/* ============================================================
   Lightbox overlay — click an image to see it large.
   openLightbox(images, startIndex) where images = [{src, caption}]
   Arrow keys / Esc work while open.
============================================================ */

function openLightbox(images, startIndex) {
    if (!images || !images.length) return;
    var el = document.getElementById('fiLightbox');
    if (!el) {
        el = document.createElement('div');
        el.id = 'fiLightbox';
        el.className = 'fi-lightbox';
        el.innerHTML =
            '<div class="fi-lightbox-backdrop"></div>' +
            '<button type="button" class="fi-lightbox-close" aria-label="Close">&times;</button>' +
            '<button type="button" class="fi-lightbox-prev" aria-label="Previous">&lsaquo;</button>' +
            '<button type="button" class="fi-lightbox-next" aria-label="Next">&rsaquo;</button>' +
            '<figure class="fi-lightbox-figure">' +
            '  <img alt="">' +
            '  <figcaption></figcaption>' +
            '</figure>' +
            '<div class="fi-lightbox-counter"></div>';
        document.body.appendChild(el);
        el.querySelector('.fi-lightbox-close').addEventListener('click', hideFiLightbox);
        el.querySelector('.fi-lightbox-backdrop').addEventListener('click', hideFiLightbox);
        el.querySelector('.fi-lightbox-prev').addEventListener('click', function () { fiLightboxStep(-1); });
        el.querySelector('.fi-lightbox-next').addEventListener('click', function () { fiLightboxStep(1); });
        document.addEventListener('keydown', function (e) {
            if (!el.classList.contains('show')) return;
            if (e.key === 'Escape') hideFiLightbox();
            if (e.key === 'ArrowLeft') fiLightboxStep(-1);
            if (e.key === 'ArrowRight') fiLightboxStep(1);
        });
    }
    el._images = images;
    el._idx = Math.max(0, Math.min(startIndex || 0, images.length - 1));
    fiLightboxRender();
    el.classList.add('show');
    document.body.style.overflow = 'hidden';
}

function hideFiLightbox() {
    var el = document.getElementById('fiLightbox');
    if (!el) return;
    el.classList.remove('show');
    document.body.style.overflow = '';
}

function fiLightboxStep(delta) {
    var el = document.getElementById('fiLightbox');
    if (!el || !el._images) return;
    el._idx = (el._idx + delta + el._images.length) % el._images.length;
    fiLightboxRender();
}

function fiLightboxRender() {
    var el = document.getElementById('fiLightbox');
    if (!el || !el._images) return;
    var img = el._images[el._idx];
    el.querySelector('img').src = img.src;
    var cap = el.querySelector('figcaption');
    cap.textContent = img.caption || '';
    cap.style.display = img.caption ? '' : 'none';
    el.querySelector('.fi-lightbox-counter').textContent =
        (el._idx + 1) + ' / ' + el._images.length;
    var multi = el._images.length > 1;
    el.querySelector('.fi-lightbox-prev').style.display = multi ? '' : 'none';
    el.querySelector('.fi-lightbox-next').style.display = multi ? '' : 'none';
}