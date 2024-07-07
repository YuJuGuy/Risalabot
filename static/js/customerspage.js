document.addEventListener('DOMContentLoaded', function () {
    // Function definitions
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

    function openAddPopup() {
        document.getElementById("eventForm").reset();
        document.getElementById("eventForm").action = eventFormActionUrl;
        document.getElementById("saveButton").innerText = "Save";
        document.getElementById("myPopup").classList.add("show");
    }

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

    // Event listeners
    const messages = document.querySelectorAll('.message');
    setTimeout(() => {
        messages.forEach(message => {
            message.classList.add('hidden');
        });
    }, 3000); // Change 3000 to the number of milliseconds you want the message to display

    const linkColor = document.querySelectorAll('.nav__link');

    function colorLink(event) {
        // Prevents the link from toggling the dropdown if it has one
        if (this.nextElementSibling && this.nextElementSibling.classList.contains('nav__dropdown-collapse')) {
            event.preventDefault();
        }
        // Remove active class from all links
        linkColor.forEach(l => l.classList.remove('active'));
        // Add active class to the clicked link
        this.classList.add('active');
    }

    linkColor.forEach(l => l.addEventListener('click', colorLink));

    document.querySelectorAll('.nav__dropdown').forEach(item => {
        item.addEventListener('click', function() {
            this.classList.toggle('active');
        });
    });

    document.getElementById("myButton").addEventListener("click", openAddPopup);

    document.getElementById("closePopup").addEventListener("click", function() {
        document.getElementById("myPopup").classList.remove("show");
    });

    window.addEventListener("click", function(event) {
        if (event.target == document.getElementById("myPopup")) {
            document.getElementById("myPopup").classList.remove("show");
        }
    });

    document.querySelectorAll('.edit-button').forEach(button => {
        button.addEventListener('click', function() {
            const eventId = this.getAttribute('data-event-id');
            const eventType = this.getAttribute('data-event-type-id');
            const subcategory = this.getAttribute('data-subcategory');
            const messageTemplate = this.getAttribute('data-message-template');
            openEditPopup(eventId, eventType, subcategory, messageTemplate);
        });
    });

    var eventTypeField = document.getElementById('id_event_type');
    eventTypeField.addEventListener('change', updateSubcategoryVisibility);

    // Initialize visibility on page load
    updateSubcategoryVisibility(); 
});
