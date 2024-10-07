from flask import Flask, render_template, request, redirect, url_for
import paramiko
import os
import threading
import time
from flask_socketio import SocketIO, emit, join_room, leave_room
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(".env.vault")

app = Flask(__name__)
socketio = SocketIO(app)

# Ensure the directory for generated images exists
if not os.path.exists('static/generated_images'):
    os.makedirs('static/generated_images')

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        prompts = [
            request.form.get('prompt1'),
            request.form.get('prompt2'),
            request.form.get('prompt3'),
            request.form.get('prompt4')
        ]
        # Start a background thread to handle image generation
        threading.Thread(target=generate_images, args=(prompts,)).start()
        return redirect(url_for('results'))
    return render_template('index.html')

@app.route('/results')
def results():
    # Get the list of images
    images = sorted(os.listdir('static/generated_images'))
    return render_template('results.html', images=images)

@socketio.on('connect')
def on_connect():
    # Join a room for the current session
    join_room('results_room')
    print('Client connected and joined results_room')

@socketio.on('disconnect')
def on_disconnect():
    leave_room('results_room')
    print('Client disconnected and left results_room')

def generate_images(prompts):
    # Remote paths
    remote_script = os.getenv('REMOTE_SCRIPT')
    remote_output_folder = os.getenv('REMOTE_OUTPUT_FOLDER')
    remote_venv_activate = os.getenv('REMOTE_VENV_ACTIVATE')

    # Remote connection variables
    gateway = os.getenv('GATEWAY')
    user = os.getenv('USER')
    password = os.getenv('PASSWORD')
    identityfile = os.getenv('IDENTITYFILE')
    host = os.getenv('HOST')
    port = os.getenv('PORT')

    # Establish SSH connection
    pkey = paramiko.RSAKey.from_private_key_file(identityfile, password=password)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    gw_client = paramiko.SSHClient()
    gw_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    gw_client.connect(hostname=gateway, port=port, username=user, password=password, sock=None, pkey=pkey)
    sock = gw_client.get_transport().open_channel(
            'direct-tcpip', (host, 22), ('', 0)
        )
    client.connect(hostname=host, port=port, username=user, password=password, sock=sock, pkey=pkey)

    # Open SFTP session
    sftp = client.open_sftp()

    for idx, prompt in enumerate(prompts):
        if prompt.strip():
            unique_filename = f'image_{idx}_{int(time.time())}.png'
            # Run the remote script with the prompt
            # Construct the remote command to source the venv and run the script
            command = (
                f"bash -c 'source {remote_venv_activate} && "
                f"accelerate launch {remote_script} --prompt \"{prompt}\" --output {unique_filename}'"
            )
            _, stdout, stderr = client.exec_command(command)

            # For debugging
            print(stdout.read().decode())
            print(stderr.read().decode())

            # Wait for the image to be generated
            remote_image_path = f"{remote_output_folder}/{unique_filename}"
            while True:
                try:
                    sftp.stat(remote_image_path)
                    break
                except IOError:
                    time.sleep(1)

            # Transfer the image
            local_image_path = f'static/generated_images/{unique_filename}'
            sftp.get(remote_image_path, local_image_path)

            # Emit socket event to update the interface, including the prompt
            socketio.emit(
                'new_image',
                {'image': unique_filename, 'prompt': prompt},
                room='results_room'
            )

    # Close connections
    sftp.close()
    client.close()

if __name__ == '__main__':
    socketio.run(app, debug=True)
