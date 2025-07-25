const chatForm = document.getElementById('chat-form');
const messageInput = document.getElementById('message-input');
const chatMessages = document.getElementById('chat-messages');

function getUserId() {
    let userId = localStorage.getItem('therapist_bot_user_id');
    if (!userId) {
        userId = prompt("به برنامه خوش آمدید! لطفاً یک شناسه کاربری برای خود وارد کنید (مثلاً: erfan123)");
        if (userId) {
            localStorage.setItem('therapist_bot_user_id', userId.trim());
        }
    }
    return userId;
}

function addMessage(text, sender) {
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', `${sender}-message`);
    const p = document.createElement('p');
    p.innerHTML = text.replace(/\n/g, '<br>'); 
    messageElement.appendChild(p);
    chatMessages.appendChild(messageElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function initializeSession(userId) {
    if (!userId) {
        addMessage("شناسه کاربری برای شروع جلسه ضروری است. لطفاً صفحه را رفرش کنید.", "bot");
        return;
    }
    chatMessages.innerHTML = '';
    addMessage('در حال اتصال به سرور و شروع جلسه...', 'bot');
    messageInput.disabled = true;

    try {
        const response = await fetch('/start', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ user_id: userId })
        });
        if (!response.ok) throw new Error('Failed to start a new session.');
        
        const data = await response.json();
        chatMessages.innerHTML = '';
        addMessage(data.initial_message, 'bot');
        messageInput.disabled = false;
        messageInput.focus();

    } catch(error) {
        addMessage(`Citical error: ${error.message}`, 'bot');
        messageInput.disabled = true;
    }
}

chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    let userId = localStorage.getItem('therapist_bot_user_id');
    if (!userId) {
        initializeSession();
        return;
    }

    const userInput = messageInput.value.trim();
    if (userInput === '') return;
    
    addMessage(userInput, 'user');
    messageInput.value = '';
    
    const typingIndicator = document.createElement('div');
    typingIndicator.classList.add('message', 'bot-message', 'typing');
    typingIndicator.innerHTML = '<p>در حال فکر کردن...</p>';
    chatMessages.appendChild(typingIndicator);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ user_id: userId, message: userInput }),
        });
        
        if (!response.ok) {
            const errorInfo = {
                status: response.status,
                message: (await response.json().catch(() => ({}))).detail || `Error ${response.status}`
            };
            throw errorInfo;
        }

        const data = await response.json();
        chatMessages.removeChild(typingIndicator); 
        addMessage(data.response, 'bot');
        
        if (data.is_session_over) {
            messageInput.disabled = true;
            messageInput.placeholder = 'جلسه به پایان رسید. برای شروع مجدد صفحه را رفرش کنید.';
            sessionStorage.removeItem('therapist_bot_user_id');
        }

    } catch (error) {
        if (chatMessages.contains(typingIndicator)) {
            chatMessages.removeChild(typingIndicator);
        }

        if (error.status === 404) {
            addMessage("اتصال شما قطع شده بود. در حال شروع یک جلسه جدید...", 'bot');
            setTimeout(() => initializeSession(), 2000);
        } else {
            addMessage(`خطا: ${error.message || 'یک خطای ناشناخته رخ داد.'}`, 'bot');
        }
    }
});

document.addEventListener('DOMContentLoaded', () => {
    const userId = getUserId();
    if (userId) {
        initializeSession(userId);
    } else {
        addMessage("شما از وارد کردن شناسه کاربری انصراف دادید. برای استفاده، صفحه را رفرش کنید.", "bot");
    }
});