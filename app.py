from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, emit
import random

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Mapping from Socket.IO session ID to (room, username)
users = {}

# Mapping from room to set of usernames currently in that room
channel_users = {}

# Mapping from channel (room) to messaging mode ("normal" or "jumbled")
channel_modes = {}  # Default will be "jumbled" if not set

@app.route('/')
def index():
    return render_template('index.html')

# Function to jumble each word separately
def jumble_message(message):
    words = message.split()
    jumbled_words = [
        ''.join(random.sample(word, len(word))) if len(word) > 1 else word
        for word in words
    ]
    return ' '.join(jumbled_words)

@socketio.on('join')
def handle_join(data):
    username = data['username']
    room = data['room']
    join_room(room)
    
    # Save user info by session ID
    users[request.sid] = (room, username)
    
    # Add user to the channel's set
    if room in channel_users:
        channel_users[room].add(username)
    else:
        channel_users[room] = {username}
    
    # For normal users, broadcast join message to the channel.
    # (Admin panel login is separate and will not show a chat window.)
    if not (username == "admin" and room == "149"):
        emit('message', f"{username} has joined the chat.", room=room)
        
        # Inform the newly joined user if others already exist
        others = channel_users[room] - {username}
        if others:
            info = "Users already in the channel: " + ', '.join(others)
            emit('message', info, to=request.sid)

@socketio.on('message')
def handle_message(data):
    # This handler is for normal chat messages only.
    username = data['username']
    room = data['room']
    original_message = data['message']
    
    # Determine the channel mode (default to "jumbled")
    mode = channel_modes.get(room, "jumbled")
    if mode == "normal":
        jumbled_message = original_message
    else:
        jumbled_message = jumble_message(original_message)
        
    # Emit an object containing both the original and jumbled message.
    emit('message', {
        'username': username,
        'original': original_message,
        'jumbled': jumbled_message
    }, room=room)

@socketio.on('admin_mode_change')
def handle_admin_mode_change(data):
    # This event is triggered from the admin panel.
    channel = data['channel']
    mode = data['mode']  # Expected values: "normal" or "jumbled"
    
    # Update the channel mode for the specified channel
    channel_modes[channel] = mode
    
    # Send a system message to the specified channel to notify users
    emit('message', f"Admin has changed channel {channel} mode to {mode}.", room=channel)

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in users:
        room, username = users[sid]
        if room in channel_users and username in channel_users[room]:
            channel_users[room].remove(username)
            if not channel_users[room]:
                del channel_users[room]
        del users[sid]
        emit('message', f"{username} has left the chat.", room=room)

if __name__ == '__main__':
    socketio.run(app, debug=True)
