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


function showMessage(message) {
    const messageDisplay = document.getElementById('message-display');
    
    messageDisplay.textContent = message; // Set message content
    messageDisplay.classList.add('show'); // Show the message

    // Hide the message after 3 seconds
    setTimeout(() => {
        messageDisplay.classList.remove('show'); // Hide the message
    }, 3000);
}
