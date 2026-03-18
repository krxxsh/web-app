import re

def update_base_html():
    with open('frontend/templates/base.html', 'r') as f:
        content = f.read()

    # Insert toast container and CSS before <!-- Custom Scripts -->
    toast_block = '''    <!-- Toast Notification Container -->
    <div id="toastContainer" class="position-fixed bottom-0 end-0 p-3" style="z-index: 1100; max-width: 400px;"></div>

    <!-- Toast Notification CSS -->
    <style>
        .toast {
            min-width: 250px;
            margin-bottom: 1rem;
            border-radius: var(--radius-md);
            box-shadow: var(--glass-shadow);
            backdrop-filter: var(--glass-blur);
            -webkit-backdrop-filter: var(--glass-blur);
            border: 1px solid var(--glass-border);
            font-family: 'Outfit', sans-serif;
            position: relative;
            opacity: 0;
            transform: translateY(20px);
            transition: all 0.3s ease;
        }
        .toast.show {
            opacity: 1;
            transform: translateY(0);
        }
        .toast-success {
            background: var(--glass-bg);
            border-left: 4px solid var(--success);
            color: var(--text-current);
        }
        .toast-error {
            background: var(--glass-bg);
            border-left: 4px solid var(--danger);
            color: var(--text-current);
        }
        .toast-warning {
            background: var(--glass-bg);
            border-left: 4px solid var(--warning);
            color: var(--text-current);
        }
        .toast-info {
            background: var(--glass-bg);
            border-left: 4px solid var(--info);
            color: var(--text-current);
        }
        .toast-header {
            background: var(--glass-bg);
            backdrop-filter: var(--glass-blur);
            -webkit-backdrop-filter: var(--glass-blur);
            border-bottom: 1px solid var(--glass-border);
            padding: 0.5rem 1rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .toast-body {
            padding: 0.5rem 1rem;
            word-wrap: break-word;
        }
        .toast-close-button {
            background: transparent;
            border: none;
            font-size: 1.25rem;
            font-weight: bold;
            line-height: 1;
            color: var(--text-current);
            opacity: 0.5;
            padding: 0;
            cursor: pointer;
            margin: 0;
        }
    </style>'''

    # We want to insert the toast_block before the line that contains '<!-- Custom Scripts -->'
    # We'll split the content by that line and then insert the toast_block in between.
    parts = content.split('<!-- Custom Scripts -->')
    if len(parts) == 2:
        new_content = parts[0] + toast_block + '\n    <!-- Custom Scripts -->' + parts[1]
        with open('frontend/templates/base.html', 'w') as f:
            f.write(new_content)
        print('Updated base.html')
    else:
        print('Could not find <!-- Custom Scripts --> in base.html')


def update_register_html():
    with open('frontend/templates/register.html', 'r') as f:
        content = f.read()

    new_script = '''            <script>
                 document.getElementById('registerForm').addEventListener('submit', async (e) => {
                     e.preventDefault();
                     const email = document.getElementById('email').value;
                     const password = document.getElementById('password').value;
                     const username = document.getElementById('username').value;
                     const role = document.getElementById('role').value;
                     const phone = document.getElementById('phone').value;
                     const submitBtn = e.target.querySelector('button[type="submit"]');
                     
                     // Show loading state
                     submitBtn.disabled = true;
                     submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Creating account...';

                     // Fallback local DEV authentication if Firebase is inactive
                     if (typeof firebase === 'undefined' || !firebase.apps.length) {
                         try {
                             const response = await fetch('/dev-register', {
                                 method: 'POST',
                                 headers: { 'Content-Type': 'application/json' },
                                 body: JSON.stringify({ email, password, username, role, phone })
                             });

                             const data = await response.json();
                             submitBtn.disabled = false;
                             submitBtn.innerHTML = 'Create Account';
                             
                             if (response.ok) {
                                 showToast('Account created successfully!', 'success');
                                 // Redirect after brief delay to show toast
                                 setTimeout(() => {
                                     window.location.href = data.redirect || ((role === 'business_owner') ? '/admin/setup_business' : '/');
                                 }, 1500);
                             } else {
                                 showToast(data.message || 'Local Dev Registration Failed', 'error');
                             }
                         } catch (err) {
                             submitBtn.disabled = false;
                             submitBtn.innerHTML = 'Create Account';
                             showToast('Server error: ' + err.message, 'error');
                         }
                         return;
                     }

                     try {
                         const userCredential = await firebase.auth().createUserWithEmailAndPassword(email, password);
                         const user = userCredential.user;
                         await user.updateProfile({ displayName: username });

                         const idToken = await user.getIdToken();

                         // Explicit sync for new users to pass role and metadata
                         const response = await fetch('/api/firebase-login', {
                             method: 'POST',
                             headers: { 'Content-Type': 'application/json' },
                             body: JSON.stringify({
                                 idToken: idToken,
                                 username: username,
                                 role: role,
                                 phone: phone
                             })
                         });

                         const data = await response.json();
                         submitBtn.disabled = false;
                         submitBtn.innerHTML = 'Create Account';
                         
                         if (response.ok) {
                             showToast('Account created successfully!', 'success');
                             // Redirect after brief delay to show toast
                             setTimeout(() => {
                                 window.location.href = data.redirect || '/';
                             }, 1500);
                         } else {
                             showToast(data.message || 'Registration failed', 'error');
                         }
                     } catch (error) {
                         submitBtn.disabled = false;
                         submitBtn.innerHTML = 'Create Account';
                         if (error.code === 'auth/email-already-in-use') {
                             if (confirm("This email is already registered. Would you like to login instead?")) {
                                 window.location.href = '/login';
                             }
                         } else {
                             showToast('Registration Failed: ' + error.message, 'error');
                         }
                     }
                 });
                 
                 // Toast utility function
                 function showToast(message, type = 'info') {
                     // Hide any existing toasts
                     const existingToasts = document.querySelectorAll('.toast');
                     existingToasts.forEach(toast => {
                         toast.classList.remove('show');
                     });
                     
                     // Create toast element
                     const toast = document.createElement('div');
                     toast.classList.add('toast', `toast-${type}`);
                     toast.innerHTML = `
                         <div class="toast-header">
                             <strong class="me-auto">${type === 'success' ? 'Success' : type === 'error' ? 'Error' : type === 'warning' ? 'Warning' : 'Info'}</strong>
                             <small>just now</small>
                             <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                         </div>
                         <div class="toast-body">
                             ${message}
                         </div>
                     `;
                     
                     // Add to container
                     const toastContainer = document.getElementById('toastContainer');
                     toastContainer.appendChild(toast);
                     
                     // Show toast
                     setTimeout(() => {
                         toast.classList.add('show');
                     }, 100);
                     
                     // Hide toast after delay
                     setTimeout(() => {
                         toast.classList.remove('show');
                         setTimeout(() => {
                             toast.remove();
                         }, 300);
                     }, 3000);
                 }
             </script>'''

    # Insert before closing body tag
    if '</body>' in content:
        new_content = content.replace('</body>', new_script + '\n    </body>')
    else:
        new_content = content + new_script

    with open('frontend/templates/register.html', 'w') as f:
        f.write(new_content)
    print('Updated register.html')