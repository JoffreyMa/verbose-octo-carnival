import os
import time
from dotenv import load_dotenv
import wikipediaapi
import json
from bs4 import BeautifulSoup
import requests
import paramiko
import stat
from generate_video import create_video_from_images, concatenate_videos_with_audio_normalization
import pandas as pd

# Load environment variables from .env file
load_dotenv(".env.vault")


def process_next_book(csv_path):
    book_processed = False
    # Load the CSV file into a DataFrame
    df = pd.read_csv(csv_path)

    # Find the first row where "Done" is False
    try:
        next_book = df[df["Done"] == False].iloc[0]
    
        # Extract the required information
        url = next_book["Wikipedia URL"]
        book_id = next_book["Book ID"]

        # Execute the predefined sequence of functions with the extracted book info
        device = "cuda:1"
        
        # Calling placeholder functions
        get_book_info(url, book_id)
        generate_ai_content(book_id, device)
        
        # Define example animation types and additional parameters
        animation_types = ['zoom', 'pan', 'pan', 'zoom', 'pan', 'zoom']
        create_video_from_images(book_id, animation_types, blur_duration=3, fps=24)
        concatenate_videos_with_audio_normalization(book_id, prefix='sub_')

        # Mark this book as processed
        df.loc[df["Book ID"] == book_id, "Done"] = True
        
        # Save the updated DataFrame back to the CSV
        df.to_csv(csv_path, index=False)

        print(f"Processed book: {book_id}")
        book_processed = True
    except IndexError:
        pass
    return book_processed


def get_book_info(url, book_id):
    output_file = f"./data/{book_id}/info.json"

    # Ensure the directory exists, create it if it doesn't
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Initialize Wikipedia API
    wiki = wikipediaapi.Wikipedia('MyProjectName (merlin@example.com)', 'en')
    page_name = url.split("/wiki/")[-1]
    page = wiki.page(page_name)

    # Possible 'Plot' section identifiers
    plot_section_ids = ["plot", "summary", "synopsis"]

    # If page is valid, try to get book name and plot summary from 'Plot' section
    plot_text = ""
    book_name = ""
    if page.exists():
        book_name = page.title
        sections = page.sections
        for section in sections:
            if any(plot_section_id in section.title.lower() for plot_section_id in plot_section_ids):
                plot_text = section.text
                break

    # Get the author from the infobox using BeautifulSoup
    author = ""
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        infobox = soup.find('table', class_='infobox')
        if infobox:
            for row in infobox.find_all('tr'):
                header = row.find('th')
                if header and 'author' in header.text.lower():
                    author = row.find('td').get_text(strip=True)
                    break

    # Compile book information
    book_info = {
        "id": book_id,
        "name": book_name,
        "author": author,
        "url": url,
        "plot": plot_text
    }

    # Save the book information to JSON file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(book_info, f, ensure_ascii=False, indent=4)

    print(f"Book information saved to {output_file}")


def sftp_mkdirs(sftp, remote_directory):
    """
    Recursively create remote directories if they don't exist.
    """
    dirs = remote_directory.split('/')
    current_dir = ''
    for dir in dirs:
        if dir:  # Ignore empty segments from leading slash
            current_dir += f'/{dir}'
            try:
                sftp.stat(current_dir)  # Check if the directory exists
            except FileNotFoundError:
                sftp.mkdir(current_dir)  # Create directory if it does not exist


def sftp_get_dir(sftp, remote_dir, local_dir):
    """
    Recursively download a directory from the remote SFTP server to the local path.
    """
    # Ensure the local directory exists
    os.makedirs(local_dir, exist_ok=True)

    # List the directory contents
    for entry in sftp.listdir_attr(remote_dir):
        remote_path = f"{remote_dir}/{entry.filename}"
        local_path = os.path.join(local_dir, entry.filename)

        if stat.S_ISDIR(entry.st_mode):  # If entry is a directory
            sftp_get_dir(sftp, remote_path, local_path)  # Recursively download the subdirectory
        else:
            sftp.get(remote_path, local_path)  # Download the file


def generate_ai_content(book, device):
    """
    Send the material file over SFTP. Then wait for completion of ai content generation.

    Parameters:
    - remote_project_path: The remote path where the file should be uploaded.
    - remote_host: The hostname of the remote server.
    - port: The port to connect to.
    - user: The username for authentication.
    - password: The password for authentication.
    - identityfile: The path to the private key file for authentication.
    """
    # Material path
    local_plot_path = f"./data/{book}/info.json"
    local_book_data_path = f"./data/{book}"

    # Remote paths
    remote_project_path = os.getenv('REMOTE_PROJECT_PATH')
    remote_done_path = remote_project_path + f"/data/{book}/done.txt"
    remote_plot_path = remote_project_path + f"/data/{book}/info.json"
    remote_book_data_path = remote_project_path + f"/data/{book}"
    remote_venv_activate = os.getenv('REMOTE_VENV_ACTIVATE')
    remote_script = os.getenv('REMOTE_SCRIPT')

    # Remote connection variables
    gateway = os.getenv('GATEWAY')
    user = os.getenv('USERSSH')
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
    
    # Ensure remote directories exist
    sftp_mkdirs(sftp, os.path.dirname(remote_plot_path))

    # Transfer the material
    # Change the following line to send the file instead of getting it
    sftp.put(local_plot_path, remote_plot_path)

    # Run the remote script
    # Construct the remote command to source the venv and run the script
    command = (
        f"bash -c 'cd {remote_project_path} && "
        f"source {remote_venv_activate} && "
        f"python {remote_script} --book \"{book}\" --device \"{device}\"'"
    )
    _, stdout, stderr = client.exec_command(command)

    # For debugging
    print(stdout.read().decode())
    print(stderr.read().decode())

    # Wait for the image to be generated
    while True:
        try:
            sftp.stat(remote_done_path)
            break
        except IOError:
            time.sleep(60)
    
    # Transfer the ai content
    # Download the directory recursively
    sftp_get_dir(sftp, remote_book_data_path, local_book_data_path)

    # Close connections
    sftp.close()
    client.close()


# url = "https://en.wikipedia.org/wiki/Dune_Messiah"
# book_id = "dune_messiah"
# device = "cuda:1"
# get_book_info(url, book_id)
# generate_ai_content(book_id, device)

# animation_types = ['zoom', 'pan', 'pan', 'zoom', 'pan', 'zoom']  # Example animation types for each image
# create_video_from_images(book_id, animation_types, blur_duration=3, fps=24) # fix in add_subtitles_and_voiceover
# concatenate_videos_with_audio_normalization(book_id, prefix='sub_')

while process_next_book("book_wikipedia_links.csv"): 
    pass