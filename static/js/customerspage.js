let allCustomers = [];
let currentPage = 1;
let rowsPerPage = 25;
let totalCustomers = 0;

document.addEventListener("DOMContentLoaded", function() {
    setupPopup();
    setupPagination();
    setupSearch();
    setupConditions();
    setupDeleteGroupPopup();
    fetchAllCustomers();
});

function setupDeleteGroupPopup() {
    const deleteGroupPopup = document.getElementById('delete-group-popup');
    const confirmDeleteButton = document.getElementById('confirm-delete-button');
    const cancelDeleteButton = document.getElementById('cancel-delete-button');
    let groupIdToDelete = null;

    // Use event delegation to handle delete link clicks
    document.body.addEventListener('click', function(event) {
        if (event.target.closest('.delete-group-link')) {
            event.preventDefault();
            groupIdToDelete = event.target.closest('.delete-group-link').dataset.groupId;
            deleteGroupPopup.style.display = 'flex';
        }
    });

    confirmDeleteButton.addEventListener('click', function() {
        if (groupIdToDelete) {
            window.location.href = `/delete-group/${groupIdToDelete}/`;
        }
    });

    cancelDeleteButton.addEventListener('click', function() {
        groupIdToDelete = null;
        deleteGroupPopup.style.display = 'none';
    });

    // Close the popup when clicking outside of it
    window.addEventListener('click', function(event) {
        if (event.target === deleteGroupPopup) {
            deleteGroupPopup.style.display = 'none';
        }
    });
}

function setupPopup() {
    const popup = document.getElementById('popup-group');
    const customersCard = document.getElementById('group-card');
    const popupClose = document.getElementById('close-popup-button');

    if (!popup || !customersCard || !popupClose) {
        console.error('Popup or necessary elements not found.');
        return;
    }

    customersCard.addEventListener('click', () => popup.classList.add('show'));
    popupClose.addEventListener('click', () => popup.classList.remove('show'));
}

function setupSearch() {
    const searchInput = document.getElementById('search');
    searchInput.addEventListener('keypress', function(event) {
        if (event.key === 'Enter') {
            event.preventDefault();
            currentPage = 1;
            filterCustomers();
        }
    });
}

function fetchAllCustomers() {
    const customersUrl = document.getElementById('data-urls').dataset.customersUrl;

    fetch(customersUrl, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.customers) {
            allCustomers = data.customers;
            totalCustomers = allCustomers.length;
            displayCustomers(allCustomers.slice(0, rowsPerPage));
            updateGroupCounts(data.group_counts, data.group_id_to_name);
            updatePaginationControls();
        } else {
            showError('Failed to load customers.');
        }

        document.querySelector('.customers-count-number').innerHTML = totalCustomers;
    })
    .catch(error => showError('Error fetching customers: ' + error));
}

function showError(message) {
    document.getElementById('customers-loading').innerHTML = message;
}

function filterCustomers() {
    const searchInput = document.getElementById('search').value.toLowerCase();
    const filteredCustomers = allCustomers.filter(customer =>
        customer.name.toLowerCase().includes(searchInput) ||
        customer.email.toLowerCase().includes(searchInput) ||
        customer.phone.toLowerCase().includes(searchInput) ||
        customer.location.toLowerCase().includes(searchInput) ||
        (customer.groups && customer.groups.some(group => group.toLowerCase().includes(searchInput)))
    );
    totalCustomers = filteredCustomers.length;
    displayCustomers(filteredCustomers.slice((currentPage - 1) * rowsPerPage, currentPage * rowsPerPage));
    updatePaginationControls();
}




function displayCustomers(customers) {
    const customersBody = document.getElementById('customers-body');
    const customersTable = document.getElementById('customers-table');
    const loadingDiv = document.getElementById('customers-loading');

    customersBody.innerHTML = '';
    loadingDiv.style.display = 'none';

    if (customers.length > 0) {
        customers.forEach(customer => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${customer.name}</td>
                <td>${customer.email}</td>
                <td>${customer.phone}</td>
                <td>${customer.location}</td>
                <td>${customer.groups.length ? customer.groups.join(', ') : 'No groups'}</td>
                <td>${customer.updated_at}</td>
            `;
            customersBody.appendChild(row);
        });
        customersTable.style.display = 'table';
    } else {
        showError('No customers found.');
    }
}

function setupPagination() {
    const rowsPerPageSelect = document.getElementById('rows-per-page');
    const prevPageButton = document.getElementById('prev-page');
    const nextPageButton = document.getElementById('next-page');

    rowsPerPageSelect.addEventListener('change', function() {
        rowsPerPage = parseInt(this.value);
        currentPage = 1;
        filterCustomers();
    });

    prevPageButton.addEventListener('click', () => changePage(-1));
    nextPageButton.addEventListener('click', () => changePage(1));
}

function changePage(delta) {
    const newPage = currentPage + delta;
    if (newPage > 0 && newPage <= Math.ceil(totalCustomers / rowsPerPage)) {
        currentPage = newPage;
        filterCustomers();
    }
}

function updatePaginationControls() {
    const prevPageButton = document.getElementById('prev-page');
    const nextPageButton = document.getElementById('next-page');

    prevPageButton.disabled = currentPage === 1;
    nextPageButton.disabled = currentPage >= Math.ceil(totalCustomers / rowsPerPage);
}

function updateGroupCounts(groupCounts, groupIdToName) {
    const groupCardsContainer = document.getElementById('group-cards-container');
    const existingCards = Array.from(groupCardsContainer.children);

    existingCards.forEach(card => {
        const groupId = card.getAttribute('data-group-id');
        if (groupCounts[groupId] !== undefined) {
            card.querySelector(`#group-${groupId}`).textContent = groupCounts[groupId];
        }
    });

    for (const [group_id, group_count] of Object.entries(groupCounts)) {
        if (!existingCards.some(card => card.getAttribute('data-group-id') === group_id)) {
            const groupCard = createGroupCard(group_id, groupIdToName[group_id], group_count);
            groupCardsContainer.appendChild(groupCard);
        }
    }
}

function createGroupCard(groupId, groupName, groupCount) {
    const groupCard = document.createElement('div');
    groupCard.classList.add('customers-card-container');
    groupCard.setAttribute('data-group-id', groupId);
    groupCard.innerHTML = `
        <div class="space">
            <a href="#" class="delete-group-link" data-group-id="${groupId}">
                <i class="fa-solid fa-xmark"></i>
            </a>
        </div>
        <div class="all-customers">
            <i class="fa-solid fa-user-group"></i>
        </div>
        <div class="customers-count">
            <span class="customers-count-title">${groupName}</span>
            <span class="customers-count-number" id="group-${groupId}">${groupCount}</span>
        </div>
    `;
    return groupCard;
}

function setupConditions() {
    const addConditionButton = document.getElementById('add-condition-button');
    const conditionsContainer = document.getElementById('conditions-container');
    const conditionTemplate = document.getElementById('condition-template').content;

    addConditionButton.addEventListener('click', function() {
        const newCondition = document.importNode(conditionTemplate, true);
        const index = conditionsContainer.children.length;
        const conditionElement = newCondition.querySelector('.condition');
        conditionElement.dataset.index = index;
        conditionElement.querySelector('select[name="condition_field"]').name = `condition_field-${index}`;
        conditionElement.querySelector('select[name="symbol_field"]').name = `symbol_field-${index}`;
        conditionElement.querySelector('input[name="value_field"]').name = `value_field-${index}`;
        conditionsContainer.appendChild(newCondition);
    });

    conditionsContainer.addEventListener('click', function(event) {
        if (event.target.classList.contains('remove-condition')) {
            event.target.parentElement.remove();
        }
    });

    conditionsContainer.addEventListener('change', function(event) {
        if (event.target.name.startsWith('symbol_field')) {
            const conditionDiv = event.target.closest('.condition');
            const valueContainer = conditionDiv.querySelector('.value-container');
            const index = conditionDiv.dataset.index;
            valueContainer.innerHTML = event.target.value === 'between' ? `
                <input type="number" name="min_value_field-${index}" class="min-value-field" placeholder="Min value" />
                <input type="number" name="max_value_field-${index}" class="max-value-field" placeholder="Max value" />
            ` : `
                <input type="number" name="value_field-${index}" class="value-field" />
            `;
        }
    });
}
