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
});


document.addEventListener('DOMContentLoaded', () => {
    const clearButton = document.getElementById('clear-notifications');
    if (clearButton) {
      clearButton.addEventListener('click', (event) => {
        event.preventDefault();

        fetch('/clear_notifications/', {
          method: 'POST',
          headers: {
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
            'Content-Type': 'application/json',
          },
        })
          .then(response => response.json())
          .then(data => {
            if (data.success) {
              showMessage(data.message, data.type);
              setTimeout(() => {
                location.reload(); // Reload page to update notifications
              }, 2000);
            } else {
              showMessage(data.message, data.type);
            }
          })
          .catch(error => console.error('Error:', error));
      });
    }
  });

document.addEventListener("DOMContentLoaded", function() {
    const items = document.querySelectorAll(".notification-drop .item");
    
    items.forEach(item => {
        item.addEventListener('click', function() {
            const ul = this.querySelector('ul');
            const clearButton = document.getElementById('clear-notifications');
            if (ul && ul !== clearButton) {
                ul.style.display = (ul.style.display === 'none' || ul.style.display === '') ? 'block' : 'none';
            }
        });
    });
});

function toggleSidenav() {
    document.getElementById("sidenavbar").classList.toggle("active");
  }


function showMessage(message, type) {
    const messageDisplay = document.getElementById('message-display');
    const messageTitle = document.getElementById('message-title');
    const messageIcon = document.getElementById('message-icon');
    const messageContent = document.getElementById('message-content');

    if (type === 'error') {
        messageIcon.innerHTML = '<i class="fa-solid fa-circle-exclamation" style="color: red;"></i>';
    } else if (type === 'success') {
        messageIcon.innerHTML = '<i class="fa-solid fa-circle-check" style="color: green;"></i>';
    } else {
        messageIcon.innerHTML = '<i class="fa-solid fa-circle-info" style="color: yellow;"></i>';
    }
    
    messageContent.textContent = message;
    messageDisplay.classList.add('show'); // Show the message

    setTimeout(() => {
        messageDisplay.classList.remove('show'); // Hide the message
    }, 3000);


}
