import sqlite3
import telebot
from config import token

bot = telebot.TeleBot(token)
# Dictionary to keep track of user states (e.g., waiting for name, waiting for phone)
user_states = {}

# ==========================================
# 2. DATABASE FUNCTIONS
# ==========================================
def init_db():
    """Initialize the SQLite database and create the contacts table if it doesn't exist."""
    conn = sqlite3.connect('phonebook.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def save_contact(name, phone):
    """Save a new contact to the database."""
    conn = sqlite3.connect('phonebook.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO contacts (name, phone) VALUES (?, ?)", (name, phone))
    conn.commit()
    conn.close()

def search_contacts(name):
    """Search for contacts by name (case-insensitive partial match)."""
    conn = sqlite3.connect('phonebook.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM contacts WHERE name LIKE ?", (f'%{name}%',))
    results = cursor.fetchall()
    conn.close()
    return results

def delete_contact(name):
    """Delete a contact by exact name match."""
    conn = sqlite3.connect('phonebook.db')
    cursor = conn.cursor()
    # We use exact match (=) instead of LIKE so we don't accidentally delete similarly named contacts
    cursor.execute("DELETE FROM contacts WHERE name = ?", (name,))
    conn.commit()
    rows_affected = cursor.rowcount # Returns how many rows were actually deleted
    conn.close()
    return rows_affected

# ==========================================
# 3. BOT COMMAND HANDLERS
# ==========================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Send a welcome message and instructions."""
    welcome_text = (
        "📖 *Welcome to the Phonebook Bot!*\n\n"
        "Here is what you can do:\n"
        "/add - Add a new contact\n"
        "/search - Search for a contact\n"
        "/delete - Delete a contact\n"
        "/cancel - Cancel current action"
    )
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

@bot.message_handler(commands=['add'])
def add_contact_name(message):
    """Start the process of adding a contact by asking for the name."""
    user_id = message.from_user.id
    user_states[user_id] = {'step': 'waiting_for_name'}
    msg = bot.reply_to(message, "Please enter the contact's *name*:", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_add_step)

def process_add_step(message):
    """Process the steps for adding a contact."""
    user_id = message.from_user.id
    
    if message.text == '/cancel':
        user_states.pop(user_id, None)
        bot.reply_to(message, "Action cancelled.")
        return

    state = user_states.get(user_id)
    if not state:
        return

    if state['step'] == 'waiting_for_name':
        name = message.text.strip()
        if not name:
            bot.reply_to(message, "Name cannot be empty. Please enter a valid name:")
            bot.register_next_step_handler(message, process_add_step)
            return
        
        user_states[user_id]['name'] = name
        user_states[user_id]['step'] = 'waiting_for_phone'
        msg = bot.reply_to(message, f"Great! Now enter the *phone number* for {name}:", parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_add_step)

    elif state['step'] == 'waiting_for_phone':
        phone = message.text.strip()
        name = state['name']
        
        save_contact(name, phone)
        bot.reply_to(message, f"✅ *Contact saved successfully!*\n\n👤 Name: {name}\n📞 Phone: {phone}", parse_mode='Markdown')
        
        user_states.pop(user_id, None)

@bot.message_handler(commands=['search'])
def search_contact(message):
    """Start the process of searching for a contact."""
    user_id = message.from_user.id
    user_states[user_id] = {'step': 'waiting_for_search_name'}
    msg = bot.reply_to(message, "Please enter the *name* of the person you want to search for:", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_search_step)

def process_search_step(message):
    """Process the search query and return results."""
    user_id = message.from_user.id
    
    if message.text == '/cancel':
        user_states.pop(user_id, None)
        bot.reply_to(message, "Action cancelled.")
        return

    state = user_states.get(user_id)
    if not state:
        return

    if state['step'] == 'waiting_for_search_name':
        search_name = message.text.strip()
        contacts = search_contacts(search_name)

        if contacts:
            response = f"🔎 *Found {len(contacts)} contact(s):*\n\n"
            for contact in contacts:
                response += f"👤 Name: {contact[1]}\n📞 Phone: {contact[2]}\n\n"
            bot.reply_to(message, response, parse_mode='Markdown')
        else:
            bot.reply_to(message, f"❌ No contacts found for '{search_name}'.")

        user_states.pop(user_id, None)

# ==========================================
# NEW: DELETE COMMAND HANDLERS
# ==========================================
@bot.message_handler(commands=['delete'])
def delete_contact_cmd(message):
    """Start the process of deleting a contact."""
    user_id = message.from_user.id
    user_states[user_id] = {'step': 'waiting_for_delete_name'}
    msg = bot.reply_to(message, "Please enter the *exact name* of the contact you want to delete:", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_delete_step)

def process_delete_step(message):
    """Process the deletion step."""
    user_id = message.from_user.id
    
    if message.text == '/cancel':
        user_states.pop(user_id, None)
        bot.reply_to(message, "Action cancelled.")
        return

    state = user_states.get(user_id)
    if not state:
        return

    if state['step'] == 'waiting_for_delete_name':
        name = message.text.strip()
        if not name:
            bot.reply_to(message, "Name cannot be empty. Please enter a valid name:")
            bot.register_next_step_handler(message, process_delete_step)
            return
        
        # Delete from database
        rows_deleted = delete_contact(name)
        
        if rows_deleted > 0:
            bot.reply_to(message, f"✅ *Contact deleted successfully!*\n\n🗑️ Removed {rows_deleted} contact(s) named '{name}'.", parse_mode='Markdown')
        else:
            bot.reply_to(message, f"❌ No contacts found with the exact name '{name}'.")
        
        # Clear user state
        user_states.pop(user_id, None)

# ==========================================
# 4. CANCEL & FALLBACK HANDLERS
# ==========================================
@bot.message_handler(commands=['cancel'])
def cancel_action(message):
    """Handle the /cancel command if triggered outside of a step."""
    user_id = message.from_user.id
    if user_id in user_states:
        user_states.pop(user_id)
        bot.reply_to(message, "Action cancelled.")
    else:
        bot.reply_to(message, "There is no active action to cancel.") 

@bot.message_handler(func=lambda message: True)
def handle_unhandled_messages(message):
    """Reply to any text that isn't a command or part of an active state."""
    if message.from_user.id not in user_states:
        bot.reply_to(message, "I didn't understand that. Please use /add, /search, or /delete.\nType /help for more info.")

# ==========================================
# 5. START THE BOT
# ==========================================
if __name__ == '__main__':
    print("Initializing database...")
    init_db()
    print("Database ready!")
    
    print("Starting bot... (Press Ctrl+C to stop)")
    bot.infinity_polling(skip_pending=True)