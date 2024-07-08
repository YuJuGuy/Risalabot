document.addEventListener('DOMContentLoaded', function() {
    // Function to hide messages after 3 seconds
    const messages = document.querySelectorAll('.message');
    setTimeout(() => {
        messages.forEach(message => {
            message.classList.add('hidden');
        });
    }, 3000);

    // Function to handle navigation link colors
    const linkColor = document.querySelectorAll('.nav__link');
    function colorLink(event) {
        if (this.nextElementSibling && this.nextElementSibling.classList.contains('nav__dropdown-collapse')) {
            event.preventDefault(); // Prevent dropdown toggle if it exists
        }
        linkColor.forEach(l => l.classList.remove('active')); // Remove active class from all links
        this.classList.add('active'); // Add active class to the clicked link
    }
    linkColor.forEach(l => l.addEventListener('click', colorLink)); // Add event listener to each link

    // Function to toggle active class on dropdown click
    document.querySelectorAll('.nav__dropdown').forEach(item => {
        item.addEventListener('click', function() {
            this.classList.toggle('active');
        });
    });

    // Function to update subcategory visibility based on event type selection
    function updateSubcategoryVisibility() {
        var eventTypeField = document.getElementById('id_event_type');
        var selectedValue = eventTypeField.value;
        var subcategoryField = document.getElementById('id_subcategory').parentElement;
        if (selectedValue == order_updated_event_type_id) {
            subcategoryField.style.display = 'block';
        } else {
            subcategoryField.style.display = 'none';
        }
    }

    // Function to open the add popup
    function openAddPopup() {
        document.getElementById("eventForm").reset();
        document.getElementById("eventForm").action = eventFormActionUrl;
        document.getElementById("saveButton").innerText = "Save";
        document.getElementById("myPopup").classList.add("show");
    }

    // Function to open the edit popup
    function openEditPopup(eventId, eventType, subcategory, messageTemplate) {
        document.getElementById("eventForm").reset();
        document.getElementById("id_event_type").value = eventType;
        document.getElementById("id_subcategory").value = subcategory;
        document.getElementById("id_message_template").value = messageTemplate;
        document.getElementById("eventForm").action = eventFormActionUrl.replace('events', `manage_event/${eventId}`);
        document.getElementById("saveButton").innerText = "Update";
        updateSubcategoryVisibility();
        document.getElementById("myPopup").classList.add("show");
    }

    // Event listener for the add button to open add popup
    document.getElementById("myButton").addEventListener("click", openAddPopup);

    // Event listener for close button to close popup
    document.getElementById("closePopup").addEventListener("click", function() {
        document.getElementById("myPopup").classList.remove("show");
    });

    // Event listener to close popup if clicked outside
    window.addEventListener("click", function(event) {
        if (event.target == document.getElementById("myPopup")) {
            document.getElementById("myPopup").classList.remove("show");
        }
    });

    // Event listener for edit buttons to open edit popup
    document.querySelectorAll('.edit-button').forEach(button => {
        button.addEventListener('click', function() {
            const eventId = this.getAttribute('data-event-id');
            const eventType = this.getAttribute('data-event-type-id');
            const subcategory = this.getAttribute('data-subcategory');
            const messageTemplate = this.getAttribute('data-message-template');
            openEditPopup(eventId, eventType, subcategory, messageTemplate);
        });
    });

    // Initialize visibility of subcategory on page load
    updateSubcategoryVisibility();

    // Event listener for change in event type to update subcategory visibility
    var eventTypeField = document.getElementById('id_event_type');
    if (eventTypeField) {
        eventTypeField.addEventListener('change', function() {
            updateSubcategoryVisibility();
        });
    }
});
