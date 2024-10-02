from flask import Flask, render_template, request, redirect, url_for
import paramiko
import os
import threading
import time

app = Flask(__name__)

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

def generate_images(prompts):
    hostname = 'your_remote_server'
    username = 'your_username'
    password = 'your_password'  # Use SSH keys for better security

    # Establish SSH connection
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, username=username, password=password)

    # Open SFTP session
    sftp = ssh.open_sftp()

    remote_script = '/path/to/remote/script.py'  # Remote script path
    remote_output_folder = '/path/to/remote/output_folder'  # Remote output folder

    for idx, prompt in enumerate(prompts):
        if prompt.strip():
            # Run the remote script with the prompt
            command = f"accelerate launch {remote_script} --prompt '{prompt}' --output image_{idx}.png"
            ssh.exec_command(command)

            # Wait for the image to be generated
            remote_image_path = f"{remote_output_folder}/image_{idx}.png"
            while True:
                try:
                    sftp.stat(remote_image_path)
                    break
                except IOError:
                    time.sleep(1)

            # Transfer the image
            local_image_path = f'static/generated_images/image_{idx}.png'
            sftp.get(remote_image_path, local_image_path)

    # Close connections
    sftp.close()
    ssh.close()

if __name__ == '__main__':
    app.run(debug=True)
