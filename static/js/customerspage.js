document.addEventListener("DOMContentLoaded", function() {
    fetchCustomers();
    const popup = document.getElementById('popup-group');
    const customersCard = document.getElementById('group-card');
    const popupClose = document.getElementById('close-popup-button');

    if (!popup) {
        console.error('Popup element not found.');
        return;
    }

    if (customersCard) {
        customersCard.addEventListener('click', function() {
            popup.classList.add('show'); // Show the popup
        });
    } else {
        console.error('Customers card container element not found.');
    }

    if (popupClose) {
        popupClose.addEventListener('click', function() {
            popup.classList.remove('show'); // Hide the popup
        });
    } else {
        console.error('Close button element not found.');
    }
});


function fetchCustomers() {
    const customersUrl = document.getElementById('data-urls').dataset.customersUrl;

    fetch(customersUrl, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        const customersTable = document.getElementById('customers-table');
        const customersBody = document.getElementById('customers-body');
        const loadingDiv = document.getElementById('customers-loading');
        const customerNumber = document.querySelector('.customers-count-number');
        const groupCardsContainer = document.getElementById('group-cards-container');
        
        // Remove loading indicator
        loadingDiv.style.display = 'none';

        // Populate the table
        if (data.customers) {
            data.customers.forEach(customer => {
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

            // Show the table
            customersTable.style.display = 'table';
        } else {
            loadingDiv.innerHTML = 'Failed to load customers.';
        }

        // Update total customer count
        customerNumber.innerHTML = data.customers.length;

        // Update group counts and names
        if (data.group_counts && data.group_id_to_name) {
            for (const [group_id, group_count] of Object.entries(data.group_counts)) {
                const group_name = data.group_id_to_name[group_id];
                const groupCard = document.createElement('div');
                groupCard.classList.add('customers-card-container');
                groupCard.innerHTML = `
                    <a href="/delete-group/${group_id}/" onclick="return confirm('Are you sure you want to delete this group?');">
                        <i class="fa-solid fa-trash"></i>
                    </a>
                    <div class="all-customers">
                        <i class="fa-solid fa-user"></i>
                    </div>
                    <div class="customers-count">
                        <span class="customers-list-title">${group_name}</span>
                        <span class="customers-list-number" id="group-${group_id}">${group_count}</span>
                    </div>
                `;
                groupCardsContainer.appendChild(groupCard);
            }
        }
    })
    .catch(error => {
        console.error('Error fetching customers:', error);
        document.getElementById('customers-loading').innerHTML = 'Failed to load customers.';
    });
}

document.addEventListener('DOMContentLoaded', function() {
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
            if (event.target.value === 'between') {
                valueContainer.innerHTML = `
                    <input type="number" name="min_value_field-${index}" class="min-value-field" placeholder="Min value" />
                    <input type="number" name="max_value_field-${index}" class="max-value-field" placeholder="Max value" />
                `;
            } else {
                valueContainer.innerHTML = `
                    <input type="number" name="value_field-${index}" class="value-field" />
                `;
            }
        }
    });
});